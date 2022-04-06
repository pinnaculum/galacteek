import time
import io
import os.path
import os
import orjson
import uuid
import aiofiles
import asyncio
import aiohttp
import re
import multiaddr

from aiohttp.web_exceptions import HTTPOk
from yarl import URL
from pathlib import Path
from datetime import datetime
from cachetools import TTLCache

from PyQt5.QtCore import QFile

import async_timeout

from galacteek.ipfs.paths import posixIpfsPath
from galacteek.ipfs.cidhelpers import joinIpfs
from galacteek.ipfs.cidhelpers import joinIpns
from galacteek.ipfs.cidhelpers import stripIpfs
from galacteek.ipfs.cidhelpers import cidConvertBase32
from galacteek.ipfs.cidhelpers import IPFSPath

from galacteek.ipfs.multi import multiAddrTcp4
from galacteek.ipfs.stat import StatInfo

from galacteek.config import cGet

from galacteek.core.asynccache import amlrucache
from galacteek.core.asynccache import cachedcoromethod
from galacteek.core.asynclib import loopTime
from galacteek.core.asynclib import async_enterable
from galacteek.core.jtraverse import traverseParser

from galacteek.core.tmpf import TmpFile
from galacteek.core.asynclib import asyncRmTree
from galacteek.ld import asyncjsonld as jsonld
from galacteek.ld.iri import ipfsPeerUrn

from galacteek import log
from galacteek import logUser
from galacteek import AsyncSignal

import aioipfs

from .nscache import IPNSCache
from .pinops import RemotePinningOps
from .pinops import RemotePinningServiceOps
from .ldops import LinkedDataOps


GFILES_ROOT_PATH = '/galacteek/'


def isDict(data):
    return isinstance(data, dict)


class OperatorError(Exception):
    pass


class UnixFSTimeoutError(Exception):
    pass


class IPFSLogWatcher(object):
    def __init__(self, operator):
        self.op = operator

    async def analyze(self):
        async for msg in self.op.client.log.tail():
            event = msg.get('event', None)

            if not event:
                continue

            if event == 'handleAddProvider':
                # Handle add provider
                if self.op.ctx:
                    self.op.ctx.logAddProvider.emit(msg)


class IPFSOperatorOfflineContext(object):
    def __init__(self, operator):
        self.operator = operator
        self.prevOff = self.operator.offline

    async def __aenter__(self):
        self.operator.offline = True
        return self.operator

    async def __aexit__(self, *args):
        self.operator.offline = self.prevOff


class GetContext(object):
    def __init__(self, operator, path, dstdir, **kwargs):
        self.operator = operator
        self.success = False
        self.path = IPFSPath(path)
        self.dstdir = Path(dstdir)
        self.finaldir = None

    async def __aenter__(self):
        try:
            await self.operator.client.core.get(
                str(self.path), dstdir=str(self.dstdir))
        except Exception as err:
            self.operator.debug(f'Unknown error: {self.path}: {err}')
            return self
        except aioipfs.APIError as err:
            self.operator.debug(f'Get error: {self.path}: {err}')
            return self
        else:
            self.success = True
            self.finaldir = self.dstdir.joinpath(self.path.basename)
            self.operator.debug(
                f'Get {self.path}: OK, fetched in {self.finaldir}')
            return self

    async def __aexit__(self, *args):
        self.operator.debug(
            f'Get {self.path}: cleaning up {self.dstdir}')
        await asyncRmTree(self.dstdir)


class TunnelDialerContext(object):
    def __init__(self, operator, peerId, proto, maddr):
        self.operator = operator
        self.peerId = peerId
        self.protocol = proto
        self.maddr = maddr

    @property
    def maddrPort(self):
        if self.maddr:
            return multiAddrTcp4(self.maddr)[1]

    @property
    def maddrHost(self):
        if self.maddr:
            return multiAddrTcp4(self.maddr)[0]

    @property
    def failed(self):
        return self.maddr is None

    def httpUrl(self, path):
        return str(URL.build(
            host=self.maddrHost,
            port=self.maddrPort,
            scheme='http',
            path=path
        ))

    async def __aenter__(self):
        self.operator.debug('Tunnel dialer: {0} {1} {2}: enter'.format(
            self.protocol, self.maddrHost, self.maddrPort))
        self.session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False))
        return self

    async def __aexit__(self, *args):
        self.operator.debug('Tunnel dialer: {0} {1} {2}: aexit'.format(
            self.protocol, self.maddrHost, self.maddrPort))

        await self.session.close()

        if not self.operator.ctx:
            return

        manager = self.operator.ctx.p2p.tunnelsMgr

        streams = await manager.streamsForListenAddr(self.maddr)
        if streams:
            # self.operator.debug(streams)
            for stream in streams:
                self.operator.debug('Tunnel dialer: closing {!r}'.format(
                    stream))
                await self.operator.client.p2p.listener_close(
                    self.protocol,
                    listen_address=self.maddr
                )


class LDOpsContext(object):
    def __init__(self, operator, ldDocLoader):
        self.operator = operator
        self.ldLoader = ldDocLoader

    async def __aenter__(self):
        return self

    async def expandDocument(self, doc):
        """
        Perform a JSON-LD expansion on a JSON document
        """

        try:
            expanded = await jsonld.expand(
                await self.operator.ldInline(doc), {
                    'documentLoader': self.ldLoader
                }
            )

            if isinstance(expanded, list) and len(expanded) > 0:
                return expanded[0]
        except jsonld.SyntaxError as serr:
            self.operator.debug(f'JSON-LD syntax error: {serr}')
            raise serr
        except Exception as err:
            self.operator.debug('Error expanding document: {}'.format(
                str(err)))

    async def dagExpandAggressive(self, ipfsPath: IPFSPath):
        """
        Aggressive expansion
        """
        try:
            dag = await self.operator.dagGet(str(ipfsPath))

            expanded = await jsonld.expand(
                await self.operator.ldInline(dag), {
                    'documentLoader': self.ldLoader
                }
            )

            if not isinstance(expanded, list):
                raise Exception('Empty expand')
        except Exception as err:
            self.operator.debug(f'Error expanding : {err}')
            raise err
        except aioipfs.APIError as err:
            self.operator.debug(f'IPFS error expanding : {err.message}')
            raise err
        else:
            return expanded

    async def __aexit__(self, *args):
        pass


class APIErrorDecoder:
    def __init__(self, exc):
        self.exc = exc

    def errIsDirectory(self):
        return self.exc.message == 'this dag node is a directory'

    def errNoSuchLink(self):
        return self.exc.message.startswith('no link named') or \
            self.exc.message == 'no such link found'

    def errUnknownNode(self):
        return self.exc.message == 'unknown node type'


# Stream-resolve cache
sResolveCache = TTLCache(512, 15)


class IPFSOperator(RemotePinningOps,
                   RemotePinningServiceOps,
                   LinkedDataOps):
    """
    IPFS operator, for your daily operations!
    """

    def __init__(self, client, ctx=None, rsaAgent=None, debug=False,
                 offline=False,
                 nsCache=None,
                 objectMapping=False):
        super().__init__()

        self._lock = asyncio.Lock()
        self._id = uuid.uuid1()
        self._cache = {}
        self._offline = offline
        self._objectMapping = objectMapping
        self._rsaAgent = rsaAgent
        self._curve25519Agent = None
        self._nsCache = nsCache if nsCache else IPNSCache(Path('ncache.json'))
        self._noPeers = True
        self._ldDocLoader = None
        self.debugInfo = debug
        self.client = client

        self.ctx = ctx

        self.filesChroot = None
        self._commands = None

        self.evReady = asyncio.Event()
        self.gotNoPeers = AsyncSignal()
        self.gotPeers = AsyncSignal(int)

        self.nsCache.nsCacheLoad()

    @property
    def nsCache(self):
        return self._nsCache

    @property
    def offline(self):
        return self._offline

    @offline.setter
    def offline(self, v):
        self._offline = v

    @property
    def noPeers(self):
        return self._noPeers

    @noPeers.setter
    def noPeers(self, v):
        self._noPeers = v

    @property
    def uid(self):
        return self._id

    @property
    def rsaAgent(self):
        return self._rsaAgent

    @property
    def curve25519Agent(self):
        return self._curve25519Agent

    @property
    def logwatch(self):
        return IPFSLogWatcher(self)

    @property
    def availCommands(self):
        """ Cached property: available IPFS commands """
        return self._commands

    @property
    def unixFsWrapRules(self):
        return cGet('unixfs.dirWrapRules',
                    mod='galacteek.ipfs')

    @property
    def cNsCache(self):
        return cGet('nsCache')

    def opConfig(self, opName):
        return cGet(f'ops.{opName}')

    def debug(self, msg):
        log.debug('IPFSOp({0}): {1}'.format(self.uid, msg))

    def info(self, msg):
        log.info('IPFSOp({0}): {1}'.format(self.uid, msg))

    def setRsaAgent(self, agent):
        self._rsaAgent = agent

    def setCurve25519Agent(self, agent):
        self._curve25519Agent = agent

    @async_enterable
    async def offlineMode(self):
        clone = IPFSOperator(self.client, ctx=self.ctx)
        return IPFSOperatorOfflineContext(clone)

    async def __aenter__(self):
        await self.client.agent_version_get()
        return self

    async def __aexit__(self, *args):
        return

    async def ipid(self):
        if self.ctx:
            curProfile = self.ctx.currentProfile
            return await curProfile.userInfo.ipIdentifier()

    async def sleep(self, t=0):
        await asyncio.sleep(t)

    async def waitReady(self, timeout=10):
        return await self.waitFor(self.evReady.wait(), timeout)

    async def waitFor(self, awaitable, timeout,
                      raiseCancelled=True):
        try:
            with async_timeout.timeout(timeout):
                return await awaitable
        except asyncio.TimeoutError:
            self.debug('Timeout waiting for coroutine {0}'.format(awaitable))
            return None
        except asyncio.CancelledError:
            self.debug('Cancelled coroutine {0}'.format(awaitable))

            if raiseCancelled:
                raise

    @amlrucache
    async def daemonConfig(self):
        try:
            return await self.client.config.show()
        except Exception:
            return None

    async def daemonConfigGet(self, attr):
        """
        Get an attribute from the daemon's config JSON document
        """
        config = await self.daemonConfig()
        if config:
            try:
                parser = traverseParser(config)
                return parser.traverse(attr)
            except Exception:
                return None

    async def getCommands(self):
        if self.availCommands is not None:
            return self.availCommands
        try:
            self._commands = await self.client.core.commands()
        except aioipfs.APIError:
            self.debug('Cannot find available IPFS commands')
            return None
        else:
            return self.availCommands

    async def filesDelete(self, path, name, recursive=False):
        try:
            await self.client.files.rm(posixIpfsPath.join(path, name),
                                       recursive=recursive)
        except aioipfs.APIError:
            self.debug('Exception on removing {0} in {1}'.format(
                name, path))
            return False
        await self.client.files.flush(path)
        return True

    async def filesLookup(self, path, name):
        """
        Looks for a file (files API) with a given name in this path

        :param str path: the path to search
        :param str name: the entry name to look for
        :return: IPFS entry
        """
        listing = await self.filesList(path)
        if listing is None:
            return
        for entry in listing:
            if entry['Name'] == name:
                return entry

    async def filesLookupHash(self, path, mhash):
        """
        Searches for a file (files API) with a given hash in this path

        :param str path: the path to search
        :param str hash: the multihash to look for
        :return: IPFS entry
        """
        listing = await self.filesList(path)
        b32CID = cidConvertBase32(mhash)

        for entry in listing:
            if cidConvertBase32(entry['Hash']) == b32CID:
                return entry

    async def filesRm(self, path, recursive=False):
        try:
            await self.client.files.rm(path, recursive=recursive)
        except aioipfs.APIError as err:
            self.debug(err.message)

    async def filesMkdir(self, path, parents=True, cidversion=1):
        try:
            await self.client.files.mkdir(
                path, parents=parents, cid_version=cidversion)
        except aioipfs.APIError as err:
            self.debug(err.message)
            return None

    async def filesMove(self, source, dest):
        try:
            return await self.client.files.mv(source, dest)
        except aioipfs.APIError as err:
            self.debug(err.message)
            return None

    async def filesList(self, path, sort=False):
        try:
            listing = await self.client.files.ls(path, long=True)
            assert listing is not None
        except aioipfs.APIError as err:
            self.debug(err.message)
            return None
        except Exception as err:
            self.debug(f'filesList ({path}): unknown error: {err}')
            return []

        if 'Entries' not in listing or listing['Entries'] is None:
            return []

        if sort is True:
            return sorted(listing['Entries'])

        return listing['Entries']

    async def filesStat(self, path, timeout=None):
        try:
            cfg = self.opConfig('filesStat')
            return await self.waitFor(
                self.client.files.stat(path),
                timeout if timeout else cfg.timeout
            )
        except aioipfs.APIError as err:
            self.debug(err.message)
            return None

    async def filesWrite(self, path, data, create=False, truncate=False,
                         offset=-1, count=-1, cidversion=1):
        try:
            await self.client.files.write(
                path, data,
                create=create, truncate=truncate,
                offset=offset, count=count,
                cid_version=cidversion
            )
        except aioipfs.APIError as err:
            self.debug('filesWrite error {}'.format(err.message))
            return None
        else:
            return True

    async def filesWriteJsonObject(self, path, obj, create=True,
                                   truncate=True):
        try:
            serialized = orjson.dumps(obj)
            resp = await self.filesWrite(path, serialized,
                                         create=create, truncate=truncate)
        except aioipfs.APIError as err:
            self.debug('filesWriteJson error {}'.format(err.message))
            return None
        else:
            return resp

    async def filesReadJsonObject(self, path):
        try:
            resp = await self.client.files.read(path)
        except aioipfs.APIError as err:
            self.debug('filesReadJson ({0}): error {1}'.format(
                path, err.message))
            return None
        except Exception as err:
            self.debug('filesReadJson ({0}): unknown error {1}'.format(
                path, str(err)))
            return None
        else:
            return orjson.loads(resp.decode())

    async def chroot(self, path):
        self.filesChroot = path

    async def vMkdir(self, path):
        if self.filesChroot:
            return await self.filesMkdir(posixIpfsPath.join(self.filesChroot,
                                                            path))

    async def vFilesList(self, path):
        if self.filesChroot:
            return await self.filesList(posixIpfsPath.join(self.filesChroot,
                                                           path))
        else:
            raise OperatorError('No chroot provided')

    async def filesCp(self, source, dest):
        try:
            await self.client.files.cp(source, dest)
        except aioipfs.APIError:
            return False

        return True

    async def filesMv(self, source, dest):
        try:
            await self.client.files.mv(source, dest)
        except aioipfs.APIError:
            return False

        return True

    async def filesLink(self, entry, dest, flush=True, name=None,
                        autoFallback=False):
        """ Given an entry (as returned by /files/ls), make a link
            in ``dest`` """

        for x in range(0, 64):
            try:
                bName = posixIpfsPath.join(
                    dest, name if name else entry['Name'])
                if autoFallback and x > 0:
                    bName += f'.{x}'

                self.debug(f'Linking {entry} to {bName}')
                await self.client.files.cp(
                    joinIpfs(entry['Hash']),
                    bName
                )
            except aioipfs.APIError:
                self.debug('Exception on copying entry {0} to {1}'.format(
                    entry, dest))

                if autoFallback:
                    continue

                else:
                    return False
            else:
                if flush:
                    await self.client.files.flush(dest)

                return True

    async def filesLinkFp(self, entry, dest):
        try:
            await self.client.files.cp(joinIpfs(entry['Hash']),
                                       dest)
        except aioipfs.APIError:
            self.debug('Exception on copying entry {0} to {1}'.format(
                entry, dest))
            return False

        return True

    async def peersList(self):
        try:
            peers = await self.client.swarm.peers()
        except aioipfs.APIError:
            self.debug('Cannot fetch list of peers')
            return []
        except Exception:
            return []
        else:
            if isDict(peers) and 'Peers' in peers:
                pList = peers['Peers']
                return pList if isinstance(pList, list) else []

    async def nodeId(self):
        info = await self.client.core.id()
        if isDict(info):
            return info.get('ID', None)

    async def nodeIdUriRef(self):
        peerId = await self.nodeId()
        if peerId:
            return ipfsPeerUrn(peerId)

    async def alive(self, timeout=5):
        nodeId = await self.waitFor(self.nodeId(), timeout,
                                    raiseCancelled=False)
        return nodeId is not None

    async def nodeWsAdresses(self):
        addrs = []
        nid = await self.client.core.id()

        for addr in nid['Addresses']:
            # use re instead of multiaddr module
            if re.search(r"/ip4/[0-9.]+/tcp/[0-9]+/ws/p2p/[\w]+", addr):
                addrs.append(addr)

        return addrs

    async def keysNames(self):
        keys = await self.keys()
        return [key['Name'] for key in keys]

    async def keyGen(self, keyName, type='rsa', keySize=2048,
                     checkExisting=False, timeout=90):
        if checkExisting is True:
            if keyName in await self.keysNames():
                return

        try:
            return await self.waitFor(
                self.client.key.gen(keyName, type=type, size=keySize), timeout
            )
        except (aioipfs.APIError, aioipfs.UnknownAPIError) as err:
            self.debug(f'Error creating key {keyName}: {err.message}')
            return False
        else:
            return True

    async def keys(self):
        kList = await self.client.key.list(long=True)
        if isDict(kList):
            return kList.get('Keys', [])

    async def keyFind(self, name, k=None):
        keys = k if k else await self.keys()
        for key in keys:
            if key['Name'] == name:
                return key

    async def keyFindById(self, ident):
        keys = await self.keys()
        for key in keys:
            if key['Id'] == ident:
                return key

    async def keysRemove(self, name):
        try:
            await self.client.key.rm(name)
        except aioipfs.APIError as err:
            self.debug('Exception on removing key {0}: {1}'.format(
                name, err.message))
            return False
        return True

    async def publish(self, path, key='self', timeout=None,
                      allow_offline=None, lifetime=None,
                      resolve=None,
                      ttl=None, cache=None, cacheOrigin='unknown'):
        cfg = self.opConfig('publish')

        usingCache = cache == 'always' or \
            (cache == 'offline' and self.noPeers and 0)

        if self.noPeers:
            aOffline = self.noPeers
        else:
            aOffline = cfg.allowOffline

        timeout = timeout if timeout else cfg.timeout
        lifetime = lifetime if lifetime else cfg.lifetime
        ttl = ttl if ttl else cfg.ttl
        resolve = resolve if isinstance(resolve, bool) else cfg.resolve

        try:
            if usingCache:
                self.debug('Caching IPNS key: {key} (origin: {origin})'.format(
                    key=key, origin=cacheOrigin))

                await self.nsCache.nsCacheSet(
                    joinIpns(key), path, origin=cacheOrigin)

            self.debug(
                f'Publishing {path} to {key} '
                f'cache: {cache}/{cacheOrigin}, allowoffline: {aOffline}, '
                f'TTL: {ttl}, lifetime: {lifetime}'
            )

            result = await self.waitFor(
                self.client.name.publish(
                    path, key=key,
                    allow_offline=aOffline,
                    lifetime=lifetime,
                    ttl=ttl,
                    resolve=resolve
                ), timeout
            )
        except aioipfs.APIError as err:
            self.debug('Error publishing {path} to {key}: {msg}'.format(
                path=path, key=key, msg=err.message))
            return None
        else:
            return result

    async def resolve(self, path, timeout=None, recursive=False):
        """
        Use /api/vx/resolve to resolve pretty much anything
        """
        cfg = self.opConfig('resolve')
        try:
            resolved = await self.waitFor(
                self.client.core.resolve(
                    await self.objectPathMapper(path),
                    recursive=recursive
                ),
                timeout if timeout else cfg.timeout
            )
        except asyncio.TimeoutError:
            self.debug('resolve timeout for {0}'.format(path))
            return None
        except aioipfs.APIError as e:
            self.debug('resolve error: {0}: {1}'.format(path, e.message))
            return None
        else:
            if isDict(resolved):
                return resolved.get('Path')

    async def noPeersFound(self):
        self.noPeers = True
        await self.gotNoPeers.emit()

    async def peersCountStatus(self, peerCount):
        self.noPeers = False
        await self.gotPeers.emit(peerCount)

    async def nameResolve(self, path,
                          timeout=None,
                          recursive=False,
                          useCache='never',
                          cache='never',
                          maxCacheLifetime=None,
                          cacheOrigin='unknown'):
        cfg = self.opConfig('nameResolve')

        timeout = timeout if timeout else cfg.timeout
        recursive = recursive if isinstance(recursive, bool) else cfg.recursive

        usingCache = useCache == 'always' or \
            (useCache == 'offline' and self.noPeers and 0)
        cache = cache == 'always' or (cache == 'offline' and self.noPeers)

        try:
            if usingCache:
                # The NS cache is used only for IPIDs when offline

                rPath = self.nsCache.nsCacheGet(
                    path, maxLifetime=maxCacheLifetime,
                    knownOrigin=True)

                if rPath and IPFSPath(rPath).valid:
                    self.debug(
                        'nameResolve: Feeding entry from NS cache: {}'.format(
                            rPath))
                    return {
                        'Path': rPath
                    }

            resolved = await self.waitFor(
                self.client.name.resolve(path, recursive=recursive),
                timeout)
        except asyncio.TimeoutError:
            self.debug('resolve timeout for {0}'.format(path))
            return None
        except aioipfs.APIError as e:
            self.debug('resolve error: {0}: {1}'.format(path, e.message))
            return None
        else:
            if cache and resolved:
                await self.nsCache.nsCacheSet(
                    path, resolved['Path'], origin=cacheOrigin)

            return resolved

    async def nameResolveStreamLegacy(self, path, count=3,
                                      timeout=20,
                                      useCache='never',
                                      cache='never',
                                      cacheOrigin='unknown',
                                      recursive=True,
                                      maxCacheLifetime=60 * 10):
        usingCache = useCache == 'always' or \
            (useCache == 'offline' and self.noPeers and 0)
        cache = cache == 'always' or (cache == 'offline' and self.noPeers)
        rTimeout = '{t}s'.format(t=timeout) if isinstance(timeout, int) else \
            timeout

        try:
            gotFromCache = False
            if usingCache:
                # The NS cache is used only for IPIDs when offline

                rPath = self.nsCache.nsCacheGet(
                    path, maxLifetime=maxCacheLifetime,
                    knownOrigin=True
                )

                if rPath and IPFSPath(rPath).valid:
                    self.debug(
                        'nameResolve: Feeding from cache: {0} for {1}'.format(
                            rPath, path))
                    yield {
                        'Path': rPath
                    }

                    gotFromCache = True

            if not gotFromCache:
                async for nentry in self.client.name.resolve_stream(
                        name=path,
                        recursive=recursive,
                        stream=True,
                        dht_record_count=count,
                        dht_timeout=rTimeout):
                    yield nentry
        except asyncio.TimeoutError:
            self.debug('streamed resolve timeout for {0}'.format(path))
        except aioipfs.APIError as e:
            self.debug('streamed resolve error: {}'.format(e.message))

    async def nameResolveStream(self, path, count=None,
                                timeout=None,
                                useCache='never',
                                cache='never',
                                cacheOrigin='unknown',
                                recursive=True,
                                maxCacheLifetime=None,
                                debug=True):
        """
        DHT is used first for resolution.
        NS cache is used as last option (used by local IPID).
        """

        cfg = self.opConfig('nameResolveStream')

        cacheCfg = self.cNsCache.origins.get(cacheOrigin)
        if not cacheCfg:
            cacheCfg = self.cNsCache.origins.unknown

        mCacheLifetime = maxCacheLifetime if maxCacheLifetime else \
            cacheCfg.maxCacheLifetime

        recCount = count if count else cfg.recordCount
        timeout = timeout if timeout else cfg.timeout

        usingCache = useCache == 'always' or \
            (useCache == 'offline' and self.noPeers and 0)
        cache = cache == 'always' or (cache == 'offline' and self.noPeers)
        rTimeout = '{t}s'.format(t=timeout) if isinstance(timeout, int) else \
            timeout
        _yieldedcn = 0

        try:
            async for nentry in self.client.name.resolve_stream(
                    name=path,
                    recursive=recursive,
                    stream=True,
                    dht_record_count=recCount,
                    dht_timeout=rTimeout):
                if cache:
                    self.debug(f'nameResolveStream ({path}): caching {nentry}')
                    await self.nsCache.nsCacheSet(
                        path, nentry['Path'], origin=cacheOrigin)

                if debug:
                    self.debug(
                        f'nameResolveStream (timeout: {timeout}) '
                        f'({path}): {nentry}')

                yield nentry
                _yieldedcn += 1
        except asyncio.TimeoutError:
            self.debug(
                f'nameResolveStream (timeout: {timeout}) '
                f'({path}): Timed out')
        except aioipfs.APIError as e:
            self.debug('nameResolveStream API error: {}'.format(e.message))
        except Exception as gerr:
            self.debug(f'nameResolveStream ({path}) unknown error: {gerr}')

        if _yieldedcn == 0 and usingCache:
            # The NS cache is used only for IPIDs when offline
            rPath = self.nsCache.nsCacheGet(
                path, maxLifetime=mCacheLifetime,
                knownOrigin=True
            )

            if rPath and IPFSPath(rPath).valid:
                self.debug(
                    'nameResolveStream: from cache: {0} for {1}'.format(
                        rPath, path))
                yield {
                    'Path': rPath
                }

    async def nameResolveStreamFirst(self, path,
                                     count=None,
                                     timeout=None,
                                     cache='never',
                                     cacheOrigin='unknown',
                                     useCache='never',
                                     maxCacheLifetime=None,
                                     debug=True):
        """
        A wrapper around the nameResolveStream async gen,
        returning the last result of the yielded values

        :rtype: dict
        """

        cfg = self.opConfig('nameResolveStreamFirst')

        recCount = count if count else cfg.recordCount
        timeout = timeout if timeout else cfg.timeout
        maxCacheLifetime = maxCacheLifetime if maxCacheLifetime else \
            cfg.maxCacheLifetime

        matches = []
        async for entry in self.nameResolveStream(
                path,
                timeout=timeout,
                count=recCount,
                cache=cache, cacheOrigin=cacheOrigin,
                maxCacheLifetime=maxCacheLifetime,
                useCache=useCache,
                debug=debug):
            found = entry.get('Path')
            if found:
                matches.append(found)

            if len(matches) >= recCount:
                break

        if len(matches) > 0:
            return {
                'Path': matches[-1]
            }

    async def objectDiff(self, obja, objb, verbose=True):
        """
        Returns the diff between two objects
        """
        try:
            diff = await self.client.object.diff(
                obja, objb, verbose=verbose)
        except aioipfs.APIError as e:
            self.debug(
                f'objectDiff error: {obja} {objb}: {e.message}')
        else:
            if isinstance(diff, dict) and 'Changes' in diff:
                return diff['Changes']

    async def purge(self, hashRef, rungc=False):
        """ Unpins an object and optionally runs the garbage collector """
        try:
            await self.client.pin.rm(hashRef, recursive=True)
            if rungc:
                await self.client.repo.gc()
            return True
        except aioipfs.APIError as e:
            self.debug('purge error: {}'.format(e.message))
            return False
        else:
            self.debug('purge OK: {}'.format(hashRef))

    async def gCollect(self, quiet=True):
        """
        Run a garbage collector sweep
        """
        return await self.client.repo.gc(quiet=quiet)

    async def isPinned(self, hashRef):
        """
        Returns True if the IPFS object referenced by hashRef is pinned,
        False otherwise
        """
        try:
            mHash = stripIpfs(hashRef)
            result = await self.client.pin.ls(multihash=mHash)
            assert isinstance(result, dict)
            keys = result.get('Keys', {})
            return mHash in keys
        except aioipfs.APIError as e:
            self.debug('isPinned error: {}'.format(e.message))
            return False
        except Exception as err:
            self.debug(f'isPinned: unknown error {err}')
            return False

    async def pinned(self, type='all'):
        """
        Returns all pinned keys of a given type
        """
        try:
            result = await self.client.pin.ls(pintype=type)
            return result.get('Keys', {})
        except aioipfs.APIError:
            return None

    async def pin(self, path, recursive=False, timeout=3600):
        async def _pin(ppath, rec):
            try:
                async for pinStatus in self.client.pin.add(
                        ppath, recursive=rec):
                    # self.debug('Pin status: {0} {1}'.format(
                    #     ppath, pinStatus))
                    pins = pinStatus.get('Pins', None)
                    if pins is None:
                        continue
                    if isinstance(pins, list) and len(pins) > 0:
                        # Ya estamos
                        return True
                return False
            except aioipfs.APIError as err:
                self.debug('Pin error: {}'.format(err.message))
                return False
        return await self.waitFor(_pin(path, recursive), timeout)

    async def pin2(self, path, recursive=True, timeout=3600):
        try:
            stcount = 0
            ltLastProg = None
            async for pinStatus in self.client.pin.add(
                    path, recursive=recursive):
                pins = pinStatus.get('Pins', None)
                progress = pinStatus.get('Progress', None)

                yield path, 0, progress

                stcount += 1
                if progress is not None:
                    ltLastProg = loopTime()

                if stcount > 32 and ltLastProg is None:
                    # Stalled ?
                    raise Exception(f'{path}: pin stalled ?')

                if pins is None:
                    continue

                if isinstance(pins, list) and len(pins) > 0:
                    # Ya estamos
                    yield path, 1, progress
                    break

        except aioipfs.APIError as err:
            self.debug('Pin error: {}'.format(err.message))
            yield path, -1, None
        except Exception as err:
            self.debug(f'Unknown pin error: {err}')
            yield path, -1, None

    async def unpin(self, obj):
        """
        Unpin an object
        """

        self.debug('unpinning: {0}'.format(obj))
        try:
            result = await self.client.pin.rm(obj)
        except aioipfs.APIError as e:
            self.debug('unpin error: {}'.format(e.message))
            return None
        else:
            self.debug('unpin success: {}'.format(result))
            return result

    async def pinUpdate(self, old, new, unpin=True):
        """
        Update a pin
        """

        try:
            result = await self.client.pin.update(old, new, unpin=unpin)
        except aioipfs.APIError as e:
            self.debug('pinUpdate error: {}'.format(e.message))
            return None
        else:
            self.debug('pinUpdate success: {}'.format(result))
            return result

    async def list(self, path, resolve_type=True):
        """
        Lists objects in a given path and yields them
        """
        try:
            listing = await self.client.ls(
                await self.objectPathMapper(path),
                headers=True,
                resolve_type=resolve_type)
            objects = listing.get('Objects', [])

            for obj in objects:
                await self.sleep()
                yield obj
        except BaseException:
            pass

    async def listStreamed(self, path, resolve_type=True, egenCount=8):
        """
        Lists objects in a UnixFS directory referenced by its
        path and yields lists of entries (8 entries by yield is
        the default).
        """
        try:
            ePack = []
            async for listing in self.client.core.ls_streamed(
                    await self.objectPathMapper(path),
                    headers=True,
                    resolve_type=resolve_type):

                objects = listing.get('Objects', [])

                for obj in objects:
                    if not isinstance(obj['Links'], list):
                        continue

                    ePack += obj['Links']

                    if len(ePack) >= egenCount:
                        yield ePack
                        ePack.clear()

                    await self.sleep()

            if len(ePack) > 0:
                # Yield remaining entries
                yield ePack
        except GeneratorExit:
            self.debug(f'listStreamed ({path}): generator exit')
            raise
        except aioipfs.APIError as e:
            self.debug(f'listStreamed ({path}): IPFS error: {e.message}')
            raise e
        except asyncio.CancelledError:
            self.debug('listStreamed ({path}): cancelled')
        except BaseException as err:
            self.debug(f'listStreamed ({path}): unknown error: {err}')
            raise err

    async def listStreamedMonitored(self, path, resolve_type=True,
                                    egenCount=16, genTimeout=10):
        eGenerator = self.listStreamed(path, resolve_type,
                                       egenCount=egenCount)

        fetching = True
        while fetching:
            try:
                entries = await self.waitFor(
                    eGenerator.__anext__(),
                    genTimeout
                )

                if entries is None:
                    # No entries were produced
                    raise UnixFSTimeoutError()

                for entry in entries:
                    yield entry
            except StopAsyncIteration:
                fetching = False

    async def objStat(self, path, timeout=30):
        try:
            stat = await self.waitFor(
                self.client.object.stat(await self.objectPathMapper(path)),
                timeout)
        except Exception:
            return None
        except aioipfs.APIError as err:
            self.debug(f'objStat {path}: error {err.message}')
            return None
        else:
            return stat

    async def objStatInfo(self, path, **kw):
        return StatInfo(await self.objStat(path, **kw))

    async def objStatCtxUpdate(self, path, timeout=30):
        exStat = self.objStatCtxGet(path)
        if exStat:
            return exStat
        try:
            self.ctx.objectStats[path] = await self.objStat(
                await self.objectPathMapper(path), timeout=timeout)
            return self.ctx.objectStats[path]
        except aioipfs.APIError:
            self.ctx.objectStats[path] = None

    def objStatCtxGet(self, path):
        return self.ctx.objectStats.get(path, None)

    async def hashComputePath(self, path, recursive=True):
        """
        Use the only-hash flag of the ipfs add command to compute
        the hash of a resource (does not add the data)
        """

        return await self.addPath(path, recursive=recursive, only_hash=True)

    async def hashComputeString(self, s, **kw):
        return await self.addString(s, only_hash=True, **kw)

    def unixFsWrapRuleMatch(self, rules, path: Path):
        isFile = path.is_file()
        isDir = path.is_dir()

        erules = sorted(
            [r for r in rules if r.enabled is True],
            reverse=True,
            key=lambda rule: rule.priority
        )
        paths = str(path)

        for rule in erules:
            if isFile and 'file' not in rule.types:
                continue
            if isDir and 'directory' not in rule.types:
                continue

            try:
                match = re.search(rule.match, paths)
                if match:
                    tr = rule.get('mfsTranslate')
                    xform = tr if tr else r'\1.dirw'

                    wName = re.sub(
                        rule.match,
                        xform,
                        path.name,
                        count=1
                    )
                    assert wName is not None

                    return rule, wName
            except Exception:
                continue

        return None, None

    async def addPath(self, path, recursive=True, wrap=False,
                      wrapAuto=False,
                      callback=None, cidversion=1, offline=False,
                      dagformat='balanced', rawleaves=False,
                      hashfunc='sha2-256',
                      pin=True, useFileStore=False,
                      ignRulesPath=None,
                      returnRoot=True,
                      rEntryFilePath=None,
                      hidden=False, only_hash=False, chunker=None):
        """
        Add files from ``path`` in the repo, and returns the top-level
        entry (the root directory), optionally wrapping it with a
        directory object

        :param str path: the path to the directory/file to import
        :param bool wrap: add a wrapping directory
        :param bool recursive: recursive import
        :param bool offline: offline mode
        :return: the IPFS top-level entry
        :rtype: dict
        """
        added = None
        returnEntry = None
        exopts = {}
        callbackvalid = asyncio.iscoroutinefunction(callback)
        origPath = Path(path)

        if not origPath.exists():
            return None

        if dagformat == 'trickle':
            exopts['trickle'] = True

        if isinstance(chunker, str):
            exopts['chunker'] = chunker

        if ignRulesPath:
            exopts['ignore_rules_path'] = ignRulesPath

        if rawleaves:
            exopts['raw_leaves'] = rawleaves

        fileStoreEnabled = await self.daemonConfigGet(
            'Experimental.FilestoreEnabled')

        goIpfsPathEnv = os.environ.get('IPFS_PATH')
        ipfsRepoPath = Path(goIpfsPathEnv) if goIpfsPathEnv else None

        if fileStoreEnabled and useFileStore and ipfsRepoPath:
            # We'll only use the filestore in standalone mode, because
            # the filestore at the moment requires symlinking from $IPFS_PATH
            #
            # Root filestore path from where we symlink
            #
            # $IPFS_PATH/_gfstore/YYYYMM/<timefloat>

            fStorePath = ipfsRepoPath.joinpath(
                '_gfstore/{sep}/{t}'.format(
                    sep=datetime.today().strftime('%Y%m'),
                    t=time.time()
                )
            )

            try:
                if not fStorePath.exists():
                    # Create the root from where we store symlinks
                    fStorePath.mkdir(parents=True)

                # Link path uses the original path's basename
                linkPath = fStorePath.joinpath(origPath.name)

                if not linkPath.exists():
                    linkPath.symlink_to(
                        path,
                        target_is_directory=origPath.is_dir()
                    )

                    # Linking OK, set the right options for the filestore
                    # Dereference symlinks when using the filestore
                    exopts['dereference_args'] = True
                    exopts['nocopy'] = True

                    # What we pass to go-ipfs now is the symlink path
                    path = str(linkPath)
            except Exception as err:
                # Can't symlink ? Won't use the filestore
                self.debug(
                    f'Error symlinking {linkPath} to the filestore: {err}')

        if wrapAuto is True:
            rule, wName = self.unixFsWrapRuleMatch(
                self.unixFsWrapRules, origPath)
            if rule:
                wrap = True

        try:
            async for entry in self.client.add(path, quiet=True,
                                               recursive=recursive,
                                               cid_version=cidversion,
                                               only_hash=only_hash,
                                               hash=hashfunc,
                                               hidden=hidden,
                                               wrap_with_directory=wrap,
                                               pin=pin,
                                               **exopts):
                await self.sleep()
                added = entry

                if returnEntry is None and rEntryFilePath == entry.get('Name'):
                    # Caller wants the entry of a specific file
                    returnEntry = entry

                if callbackvalid:
                    try:
                        await callback(entry)
                    except Exception as cbError:
                        self.debug(f'addPath error on callback: {cbError}')
                        continue
        except aioipfs.APIError as err:
            self.debug('addPath: {path}: API error: {e}'.format(
                path=path, e=err.message))
            return None
        except asyncio.CancelledError:
            self.debug('addPath: cancelled')
            return None
        except Exception as e:
            self.debug('addPath: unknown exception {}'.format(str(e)))
            return None
        else:
            if not returnEntry:
                returnEntry = added

            # self.debug(f'addPath({path}): root is {added} '
            #            f'(returning {returnEntry}')
            return returnEntry

    async def addFileEncrypted(self, path):
        basename = os.path.basename(path)
        buffSize = 262144
        readTotal = 0
        whole = io.BytesIO()

        try:
            async with aiofiles.open(path, 'rb') as fd:
                while True:
                    buff = await fd.read(buffSize)
                    if not buff:
                        break
                    await self.sleep()
                    readTotal += len(buff)
                    whole.write(buff)
        except:
            self.debug('Error occured while encrypting {path}'.format(
                path=path))
        else:
            whole.seek(0, 0)
            logUser.info('{n}: encrypting'.format(n=basename))
            return await self.rsaAgent.storeSelf(whole)

    async def addBytes(self, data, cidversion=1, **kw):
        try:
            return await self.client.core.add_bytes(
                data, cid_version=cidversion, **kw)
        except aioipfs.APIError as err:
            self.debug(err.message)
            return None

    async def addString(self, string, cidversion=1, **kw):
        try:
            return await self.client.core.add_str(
                string, cid_version=cidversion, **kw)
        except aioipfs.APIError as err:
            self.debug(err.message)
            return None

    async def addJson(self, obj, cidversion=1, **kw):
        try:
            return await self.client.core.add_bytes(
                orjson.dumps(obj),
                cid_version=cidversion, **kw)
        except aioipfs.APIError as err:
            self.debug(err.message)
            return None

    async def getJson(self, cid, timeout=30):
        try:
            data = await self.catObject(cid, timeout=timeout)
            return orjson.loads(data.decode())
        except aioipfs.APIError as err:
            self.debug(err.message)
            return None
        except Exception:
            self.debug(f'Cannot load JSON from CID {cid}')
            pass

    async def importQtResource(self, path):
        rscFile = QFile(':{0}'.format(path))

        try:
            rscFile.open(QFile.ReadOnly)
            data = rscFile.readAll().data()
            entry = await self.addBytes(data)
        except Exception as e:
            self.debug('importQtResource: {}'.format(str(e)))
        else:
            return entry

    async def closestPeers(self):
        peers = []
        try:
            info = await self.client.core.id()
            async for queryR in self.client.dht.query(info['ID']):
                responses = queryR.get('Responses', None)
                if not responses:
                    return None
                for resp in responses:
                    peers.append(resp['ID'])
            return peers
        except aioipfs.APIError:
            return None

    async def jsonLoad(self, path):
        try:
            data = await self.client.cat(path)
            return orjson.loads(data)
        except aioipfs.APIError as err:
            self.debug(err.message)
            return None

    def ipld(self, cid):
        if isinstance(cid, str):
            return {"/": cid}
        elif isinstance(cid, dict) and 'Hash' in cid:
            return {"/": cid['Hash']}

    @cachedcoromethod(sResolveCache)
    async def objectPathMapCacheResolve(self, path):
        """
        Simple async TTL cache for results from nameResolveStreamFirst()
        """
        return await self.nameResolveStreamFirst(path, debug=False)

    def sResolveCacheClear(self, time=None):
        sResolveCache.expire(time)

    def sResolveCacheLog(self):
        self.debug('sResolveCacheDump: start')

        for path, r in sResolveCache.items():
            self.debug(f'sResolveCache: path {path} => {r}')

        self.debug('sResolveCacheDump: end')

    async def objectPathMapper(self, path):
        ipfsPath = path if isinstance(path, IPFSPath) else \
            IPFSPath(path, autoCidConv=True)

        if ipfsPath.isIpns:
            resolved = await self.objectPathMapCacheResolve(path)

            if resolved:
                return resolved['Path']
            else:
                self.debug(
                    'objectPathMapper: {o}: stream-resolve failed'.format(
                        o=path))

        return path

    async def catObject(self, path, offset=None, length=None, timeout=None):
        cfg = self.opConfig('catObject')

        return await self.waitFor(
            self.client.cat(
                await self.objectPathMapper(path),
                offset=offset, length=length
            ), timeout if timeout else cfg.timeout
        )

    async def listObject(self, path, timeout=None):
        cfg = self.opConfig('listObject')
        try:
            return await self.waitFor(
                self.client.core.ls(
                    await self.objectPathMapper(path)
                ), timeout if timeout else cfg.timeout
            )
        except (aioipfs.APIError, aioipfs.UnknownAPIError):
            pass

    async def walk(self, path):
        """
        Walks over UnixFS nodes and yields only paths of
        file objects.
        """
        try:
            result = await self.listObject(path)
        except aioipfs.APIError:
            pass
        else:
            _olist = result.get('Objects', [])
            if len(_olist) > 0:
                links = _olist.pop()['Links']

                for entry in links:
                    if entry['Type'] == 1:
                        async for value in self.walk(entry['Hash']):
                            yield value
                    elif entry['Type'] == 2:
                        fPath = IPFSPath(path).child(entry['Name'])
                        if fPath.valid:
                            yield (str(fPath), path)

    async def dagPut(self, data, pin=True, offline=False):
        """
        Create a new DAG object from data and returns the root CID of the DAG
        """
        with TmpFile() as dagFile:
            try:
                dagFile.write(orjson.dumps(data))
            except Exception as e:
                self.debug('Cannot convert DAG object: {}'.format(str(e)))
                return None

            dagFile.seek(0, 0)
            try:
                output = await self.client.dag.put(
                    dagFile.name, pin=pin, offline=offline)

                if isinstance(output, dict) and 'Cid' in output:
                    return output['Cid'].get('/', None)
                else:
                    self.debug('dagPut: no CID in output')
                    return None
            except aioipfs.APIError as err:
                self.debug(f'dagPut error: {err.message}')
                return None

    async def dagPutOffline(self, data, pin=False):
        """
        Offline DAG put operation
        """
        return await self.dagPut(data, pin=pin, offline=True)

    async def dagGet(self, dagPath, timeout=30):
        """
        Get the DAG object referenced by the DAG path and returns a JSON object
        """

        output = await self.waitFor(
            self.client.dag.get(await self.objectPathMapper(dagPath)), timeout)

        if output is not None:
            return orjson.loads(output)
        else:
            self.debug(f'dagGet: {dagPath} seems invalid')

    async def dagStatBlocks(self, cid, timeout=360):
        # TODO
        # { 'Size': .., 'NumBlocks': ... }

        last = None

        async for stat in self.client.dag.stat(cid, progress=True):
            last = stat

        if last:
            return last['NumBlocks']

    async def dagResolve(self, dagPath):
        """
        Resolve DAG path and return CID if path is valid and rempath empty,
        None otherwise

        Relying on RemPath is tricky and should be changed asap
        """
        try:
            resolved = await self.client.dag.resolve(dagPath)
            log.debug('dagResolve {0} {1}'.format(dagPath, resolved))
            if isDict(resolved):
                return resolved['Cid'].get('/', None) if \
                    resolved['RemPath'] == '' else None
        except aioipfs.APIError as err:
            self.debug(err.message)
            return None

    async def findProviders(self, cid, peers, verbose, nproviders):
        """
        Don't call directly, use whoProvides instead

        :param str cid: CID key to lookup
        :param list peers: a list that will be updated with the peers found
        :param int nproviders: max number of providers to look for
        """
        try:
            self.debug('finding providers for: {}'.format(cid))

            async for prov in self.client.dht.findprovs(
                    cid, verbose=verbose,
                    numproviders=nproviders):
                pResponses = prov.get('Responses', None)
                pType = prov.get('Type', None)

                if pType != 4:  # WTF++
                    continue

                if isinstance(pResponses, list):
                    peers += pResponses
            return True
        except aioipfs.APIError as err:
            self.debug('findProviders: {}'.format(str(err.message)))
            return False
        except Exception as gerr:
            self.debug('findProviders: unknown error: {}'.format(
                str(gerr)))

    async def whoProvides(self, path, numproviders=20, timeout=20):
        """
        Return a list of peers which provide a given key, using the DHT
        'findprovs' API call.

        Because go-ipfs's findprovs will keep looking on the dht until it
        reaches the given numproviders, we use wait_for and a timeout so that
        you always get some information about the providers.

        :param int numproviders: max number of providers to look for
        :param int timeout: timeout (seconds)
        """

        peers = []
        try:
            resolved = await self.resolve(path)

            if not resolved:
                raise Exception(f'Cannot resolve {path}')

            await self.waitFor(
                self.findProviders(resolved, peers, True,
                                   numproviders), timeout)
        except asyncio.TimeoutError:
            # It timed out ? Return what we got
            self.debug('whoProvides: timed out')
            return peers
        except Exception:
            return peers

        return peers

    async def provide(self, multihash, recursive=False,
                      timeout=60):
        """
        Announce to the network that we are providing this multihash

        :param str multihash: The multihash to announce
        :param bool recursive: Recursively provide the whole graph
        """
        provideRespCount = 0
        try:
            # Not much exception handling here.. if we get out of the
            # async generator alive, we consider that it's a success
            with async_timeout.timeout(timeout):
                async for resp in self.client.dht.provide(
                        multihash, recursive=recursive):
                    if not isinstance(resp, dict):
                        continue

                    provideRespCount += 1
                    await self.sleep()

            self.debug('DHT provide {multihash}: {count} messages'.format(
                multihash=multihash, count=provideRespCount))

            return True
        except (asyncio.TimeoutError, Exception):
            return False
        except aioipfs.APIError:
            return False

    async def pingWrapper(self, peer, count=3):
        """
        Peer ping async generator, used internally by the operator for specific
        ping functions.

        Items yielded are tuples of the form (time, success, text) where time
        is the latency for the ping packet, success is boolean (True if ping
        ok) and text is the ping message

        :param str peer: Peer ID
        :param int count: ping count
        """

        async for pingReply in self.client.core.ping(peer, count=count):
            if pingReply is None:
                break

            pTime = pingReply.get('Time', None)
            pSuccess = pingReply.get('Success', None)
            pText = pingReply.get('Text', '')

            self.debug('PING: {peer} ({time}) {text} {success}'.format(
                peer=peer, time=pTime, text=pText,
                success='OK' if pSuccess is True else 'ERR'))

            yield (pTime, pSuccess, pText.strip())

            await self.sleep()

    async def pingLowest(self, peer, count=3):
        """
        Return lowest ping latency for a peer

        :param str peer: Peer ID
        :param int count: ping count
        """

        lowest = 0
        try:
            async for pTime, success, text in self.pingWrapper(
                    peer, count=count):
                if lowest == 0 and pTime != 0 and success is True:
                    lowest = pTime
                if pTime > 0 and pTime < lowest and success is True:
                    lowest = pTime
        except aioipfs.APIError:
            return 0
        else:
            return lowest

    async def pingAvg(self, peer, count=3):
        """
        Return average ping latency for a peer in msecs

        :param str peer: Peer ID
        :param int count: ping count
        :return: average latency in milliseconds or 0 if ping failed
        """

        received = []

        try:
            async for pTime, success, text in self.pingWrapper(
                    peer, count=count):
                if pTime != 0 and success is True:
                    received.append(pTime)
        except aioipfs.APIError:
            return 0

        if len(received) > 0:
            return float((sum(received) / len(received)) / 1000000)
        else:
            return 0

    async def rsaPubKeyCheckImport(self, pubKeyCid: str, pin=True):
        from galacteek.ipfs import kilobytes
        try:
            pubKeyStatInfo = await self.objStatInfo(pubKeyCid)
            if not pubKeyStatInfo.valid or \
                    pubKeyStatInfo.dataLargerThan(kilobytes(32)):
                return False

            pubKeyPem = await self.catObject(pubKeyCid, timeout=15)

            if not pubKeyPem:
                raise Exception(
                    f'Cannot fetch pubkey with CID: {pubKeyCid}')

            if pin:
                await self.pin(pubKeyCid, recursive=False, timeout=10)

            return pubKeyPem
        except aioipfs.APIError as err:
            self.debug(err.message)
            return None
        except Exception as err:
            self.debug(f'Err: {err}')
            return None

    async def pubsubPeers(self, topic=None, timeout=10):
        try:
            resp = await self.waitFor(self.client.pubsub.peers(
                topic=topic), timeout)
            return resp['Strings']
        except aioipfs.APIError as err:
            self.debug(err.message)
            return None
        except Exception as err:
            self.debug(f'pubsubPeers error: {err}')
            return None

    async def swarmBan(self, peerId: str):
        """
        Add a swarm filter for a given peer.
        """
        try:
            pInfo = await self.client.core.id(peerId)
            maddrs = pInfo['Addresses']

            for addr in maddrs:
                m = multiaddr.Multiaddr(addr)
                ip = m.value_for_protocol('ip4')

                if not ip or ip in ['127.0.0.1', '::1']:
                    continue

                await self.client.swarm.filters_add(
                    f'/ip4/{ip}/ipcidr/32'
                )
        except Exception:
            pass

    async def versionNum(self):
        try:
            vInfo = await self.client.core.version()
            return vInfo.get('Version', None)
        except aioipfs.APIError as err:
            self.debug(err.message)
            return None

    async def hasCommand(self, name, subcmd=None):
        """
        Determines whether a given command is available on this IPFS daemon,
        and if specified, if a subcommand of this command is available.

        :param str name: command name
        :param str subcmd: subcommand name
        """
        try:
            availCmds = await self.getCommands()
            if availCmds is None:
                return False

            for command in availCmds['Subcommands']:
                if subcmd is not None:
                    for subcommand in command['Subcommands']:
                        if subcommand['Name'] == subcmd:
                            return True
                if command['Name'] == name and subcmd is None:
                    return True
            return False
        except aioipfs.APIError as err:
            self.debug(err.message)
            return False

    def ourNode(self, peerId):
        return self.ctx.node.id == peerId

    def p2pEndpoint(self, serviceName: str, protocolVersion='1.0.0'):
        from galacteek.ipfs.p2pservices import p2pEndpointMake

        return p2pEndpointMake(
            self.ctx.node.id,
            serviceName,
            protocolVersion
        )

    def p2pEndpointExplode(self, addr):
        ma = re.search(r'/p2p/([\w]{46,59})/x/([\w\-\_]{1,128})', addr)
        if ma:
            return ma.group(1), ma.group(2)
        else:
            return None, None

    def p2pEndpointAddrExplode(self, addr: str):
        from galacteek.ipfs.p2pservices import p2pEndpointAddrExplode

        return p2pEndpointAddrExplode(addr)

    async def hasDagCommand(self):
        return await self.hasCommand('dag')

    async def hasP2PCommand(self):
        return await self.hasCommand('p2p')

    async def _p2pDialerStart(self, peer, proto, address,
                              allowLoopback=False):
        """
        Start the P2P dial and return a TunnelDialerContext
        """
        from galacteek.ipfs.tunnel import P2PTunnelsManager

        log.debug('Stream dial {0} {1}'.format(peer, proto))

        if allowLoopback is True:
            #
            # P2P loopback allowed
            #
            # This handles the cases where we want to be able to dial
            # local P2P services (IPFS correctly prevents this ...).
            # This is only used for now by the gemini-ipfs bridge
            #

            mgr = P2PTunnelsManager()

            nid = await self.nodeId()
            streams = await mgr.streamsForProtocol(proto)

            if nid == peer and streams and len(streams) == 1:
                # The PeerId matches and we found the stream

                taddr = streams.pop()['TargetAddress']
                log.debug(f'P2P loopback allowed for proto {proto}:'
                          f' maddr is {taddr}')
                return TunnelDialerContext(self, peer, proto, taddr)
        try:
            peerAddr = joinIpfs(peer) if not peer.startswith('/ipfs/') else \
                peer
            resp = await self.client.p2p.dial(proto, address, peerAddr)
        except aioipfs.APIError as err:
            log.debug('Stream dial error: {}'.format(err.message))
            return TunnelDialerContext(self, peer, proto, None)
        else:
            log.debug(f'Stream dial {peer} {proto}: OK')

        if resp:
            maddr = resp.get('Address', None)

            if not maddr:
                log.debug(
                    f'Stream dial {peer} {proto}: no multiaddr returned!')
                return TunnelDialerContext(self, peer, proto, None)

            ipaddr, port = multiAddrTcp4(maddr)

            if ipaddr is None or port == 0:
                return TunnelDialerContext(self, peer, proto, None)

            return TunnelDialerContext(self, peer, proto, maddr)
        else:
            return TunnelDialerContext(self, peer, proto, address)

    @async_enterable
    async def p2pDialer(self, peer, protocol, address=None, addressAuto=True):
        from galacteek.core import unusedTcpPort
        from galacteek.ipfs.tunnel import protocolFormat

        if addressAuto is True and not address:
            address = '/ip4/127.0.0.1/tcp/{}'.format(unusedTcpPort())

        if await self.client.agent_version_post0418():
            proto = protocolFormat(protocol)
        else:
            proto = protocol

        return await self._p2pDialerStart(peer, proto, address)

    @async_enterable
    async def p2pDialerFromAddr(self, p2pEndpointAddr,
                                address=None, addressAuto=True,
                                allowLoopback=False):
        from galacteek.core import unusedTcpPort
        from galacteek.ipfs.p2pservices import p2pEndpointAddrExplode

        if addressAuto is True and not address:
            address = '/ip4/127.0.0.1/tcp/{}'.format(unusedTcpPort())

        exploded = p2pEndpointAddrExplode(p2pEndpointAddr)

        if exploded:
            peerId, protoFull, pVersion = exploded

            return await self._p2pDialerStart(
                peerId, protoFull, address,
                allowLoopback=allowLoopback
            )
        else:
            raise ValueError(f'Invalid P2P service address: {p2pEndpointAddr}')

    @async_enterable
    async def getContexted(self, path, dstdir, **kwargs):
        return GetContext(self, path, dstdir, **kwargs)


class IPFSOpRegistry:
    _registry = {}
    _key_default = 0

    @staticmethod
    def reg(key, inst):
        IPFSOpRegistry._registry[key] = inst

    @staticmethod
    def get(key):
        return IPFSOpRegistry._registry.get(key, None)

    @staticmethod
    def regDefault(inst):
        return IPFSOpRegistry.reg(IPFSOpRegistry._key_default, inst)

    @staticmethod
    def getDefault():
        return IPFSOpRegistry._registry.get(IPFSOpRegistry._key_default)


class GalacteekOperator(IPFSOperator):
    """
    Extend IPFSOperator with stuff specific to galacteek
    like P2P tunnel calls
    """

    async def didPing(self, peerId, did, token):
        """
        Does a POST on /didping on the didauth-vc-pss P2P service

        Returns a tuple (ms, pongPayload)
        """
        req = {
            'did': did,
            'ident_token': token
        }

        try:
            log.debug(f'didPing({did}) for peer {peerId} with token: {token}')

            async with self.p2pDialer(
                    peerId, 'didauth-vc-pss',
                    addressAuto=True) as sCtx:
                if sCtx.failed:
                    log.debug(f'didPing({did}): failed to connect')
                    return -1, None

                startt = self.client.loop.time()
                async with sCtx.session.post(
                        sCtx.httpUrl('/didping'),
                        json=req) as resp:

                    diff = self.client.loop.time() - startt
                    if resp.status != HTTPOk.status_code:
                        raise Exception(f'DID Ping error for {did}')

                    payload = await resp.json()
                    assert isinstance(payload['didpong'], dict)
                    assert did in payload['didpong']

                    return diff * 1000, payload
        except Exception as err:
            log.debug(f'didPing error: {err}')
            return -1, None

    async def videoRendezVous(self, didService):
        remotePeerId, serviceName = self.p2pEndpointExplode(
            didService.endpoint)

        req = {
            'peer': self.ctx.node.id
        }

        try:
            async with self.p2pDialer(
                    remotePeerId, serviceName,
                    addressAuto=True) as sCtx:
                if sCtx.failed:
                    raise Exception(f'Cannot reach {remotePeerId}')

                async with sCtx.session.post(
                        sCtx.httpUrl('/rendezVous'),
                        json=req) as resp:

                    payload = await resp.json()
                    return payload['topic']
        except Exception as err:
            self.debug(str(err))
            return None
