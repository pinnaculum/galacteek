import os.path
import json
import tempfile
import uuid

from async_generator import async_generator, yield_

from galacteek.ipfs.cidhelpers import joinIpfs
from galacteek.ipfs.cidhelpers import stripIpfs
from galacteek import log

import aioipfs
import asyncio

GFILES_ROOT_PATH = '/galacteek/'


def isDict(data):
    return isinstance(data, dict)


class OperatorError(Exception):
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


class IPFSOperator(object):
    """
    IPFS operator, for your daily operations!
    """

    def __init__(self, client, ctx=None, debug=False):
        self._id = uuid.uuid1()
        self._cache = {}
        self.client = client
        self.debugInfo = debug
        self.ctx = ctx

        self.filesChroot = None
        self._commands = None

        self.evReady = asyncio.Event()

    @property
    def uid(self):
        return self._id

    @property
    def logwatch(self):
        return IPFSLogWatcher(self)

    @property
    def availCommands(self):
        """ Cached property: available IPFS commands """
        return self._commands

    def debug(self, msg):
        log.debug('IPFSOp({0}): {1}'.format(self.uid, msg))

    async def __aenter__(self):
        await self.client.agent_version_get()
        return self

    async def __aexit__(self, *args):
        return

    async def sleep(self, t=0):
        await asyncio.sleep(t)

    async def waitReady(self, timeout=10):
        return await self.waitFor(self.evReady.wait(), timeout)

    async def waitFor(self, fncall, timeout):
        try:
            output = await asyncio.wait_for(fncall, timeout)
        except asyncio.TimeoutError:
            self.debug('Timeout waiting for coroutine {0}'.format(fncall))
            return None
        else:
            return output

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
            await self.client.files.rm(os.path.join(path, name),
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

    async def filesLookupHash(self, path, hash):
        """
        Searches for a file (files API) with a given hash in this path

        :param str path: the path to search
        :param str hash: the multihash to look for
        :return: IPFS entry
        """
        listing = await self.filesList(path)
        for entry in listing:
            if entry['Hash'] == hash:
                return entry

    async def filesRm(self, path, recursive=False):
        try:
            await self.client.files.rm(path, recursive=recursive)
        except aioipfs.APIError as err:
            self.debug(err.message)
            return None

    async def filesMkdir(self, path, parents=True):
        try:
            await self.client.files.mkdir(path, parents=parents)
        except aioipfs.APIError as err:
            self.debug(err.message)
            return None

    async def filesMove(self, source, dest):
        try:
            return await self.client.files.mv(source, dest)
        except aioipfs.APIError as err:
            self.debug(err.message)
            return None

    async def filesList(self, path):
        try:
            listing = await self.client.files.ls(path, long=True)
        except aioipfs.APIError as err:
            self.debug(err.message)
            return None

        if 'Entries' not in listing or listing['Entries'] is None:
            return []

        return listing['Entries']

    async def filesStat(self, path):
        try:
            return await self.client.files.stat(path)
        except aioipfs.APIError as err:
            self.debug(err.message)
            return None

    async def filesWrite(self, path, data, create=False, truncate=False,
                         offset=-1, count=-1):
        try:
            await self.client.files.write(
                path, data,
                create=create, truncate=truncate,
                offset=offset, count=count
            )
        except aioipfs.APIError as err:
            self.debug('filesWrite error {}'.format(err.message))
            return None
        else:
            return True

    async def filesWriteJsonObject(self, path, obj, create=True,
                                   truncate=True):
        try:
            serialized = json.dumps(obj).encode()
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
            self.debug('filesReadJson error {}'.format(err.message))
            return None
        except Exception as err:
            self.debug('filesReadJson unknown error {}'.format(str(err)))
            return None
        else:
            return json.loads(resp.decode())

    async def chroot(self, path):
        self.filesChroot = path

    async def vMkdir(self, path):
        if self.filesChroot:
            return await self.filesMkdir(os.path.join(self.filesChroot,
                                                      path))

    async def vFilesList(self, path):
        if self.filesChroot:
            return await self.filesList(os.path.join(self.filesChroot,
                                                     path))
        else:
            raise OperatorError('No chroot provided')

    async def filesCp(self, srcHash, dest):
        try:
            await self.client.files.cp(joinIpfs(srcHash),
                                       dest)
        except aioipfs.APIError:
            return False

        return True

    async def filesLink(self, entry, dest, flush=True, name=None):
        """ Given an entry (as returned by /files/ls), make a link
            in dest """

        try:
            await self.client.files.cp(
                joinIpfs(entry['Hash']),
                os.path.join(dest, name if name else entry['Name'])
            )
        except aioipfs.APIError:
            self.debug('Exception on copying entry {0} to {1}'.format(
                entry, dest))
            return False

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
            return None

        if isDict(peers) and 'Peers' in peers:
            return peers['Peers']

    async def nodeId(self):
        info = await self.client.core.id()
        if isDict(info):
            return info.get('ID', 'Unknown')

    async def keysNames(self):
        keys = await self.keys()
        return [key['Name'] for key in keys]

    async def keyGen(self, keyName, type='rsa', keySize=2048):
        return await self.waitFor(
            self.client.key.gen(keyName,
                                type=type, size=keySize), 30
        )

    async def keys(self):
        kList = await self.client.key.list(long=True)
        if isDict(kList):
            return kList.get('Keys', [])

    async def keyFind(self, name):
        keys = await self.keys()
        for key in keys:
            if key['Name'] == name:
                return key

    async def keysRemove(self, name):
        try:
            await self.client.key.rm(name)
        except aioipfs.APIError as err:
            self.debug('Exception on removing key {0}: {1}'.format(
                name, err.message))
            return False
        return True

    async def publish(self, path, key='self', timeout=90):
        try:
            return await self.waitFor(self.client.name.publish(path, key=key),
                                      timeout)
        except aioipfs.APIError:
            return None

    async def resolve(self, path, timeout=20, recursive=False):
        try:
            resolved = await asyncio.wait_for(
                self.client.name.resolve(path, recursive=recursive),
                timeout)
        except asyncio.TimeoutError:
            self.debug('resolve timeout for {0}'.format(path))
            return None
        except aioipfs.APIError as e:
            self.debug('resolve error: {}'.format(e.message))
            return None
        else:
            return resolved

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

    async def isPinned(self, hashRef):
        """
        Returns True if the IPFS object referenced by hashRef is pinned,
        False otherwise
        """
        try:
            mHash = stripIpfs(hashRef)
            result = await self.client.pin.ls(multihash=mHash)
            keys = result.get('Keys', {})
            return mHash in keys
        except aioipfs.APIError as e:
            self.debug('isPinned error: {}'.format(e.message))
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

    async def pin(self, path, timeout=3600):
        async def _pin(ppath):
            async for pinStatus in self.client.pin.add(ppath):
                self.debug('Pin status: {0} {1}'.format(
                    ppath, pinStatus))
                pins = pinStatus.get('Pins', None)
                if pins is None:
                    continue
                if isinstance(pins, list) and ppath in pins:
                    # Ya estamos
                    return True
            return False
        return await self.waitFor(_pin(path), timeout)

    async def pinUpdate(self, old, new, unpin=True):
        """
        Update a pin
        """

        self.debug('pinUpdate: prev {0} new {1}'.format(old, new))
        try:
            result = await self.client.pin.update(old, new, unpin=unpin)
        except aioipfs.APIError as e:
            self.debug('pinUpdate error: {}'.format(e.message))
            return None
        else:
            self.debug('pinUpdate success: {}'.format(result))
            return result

    @async_generator
    async def list(self, path, resolve_type=True):
        """
        Lists objects in a given path and yields them
        """
        try:
            listing = await self.client.ls(path, headers=True,
                                           resolve_type=resolve_type)
            objects = listing.get('Objects', [])

            for obj in objects:
                await self.sleep()
                await yield_(obj)
        except BaseException:
            pass

    async def objStat(self, path, timeout=30):
        try:
            stat = await asyncio.wait_for(self.client.object.stat(path),
                                          timeout)
        except Exception:
            return None
        else:
            return stat

    async def objStatCtxUpdate(self, path, timeout=30):
        try:
            self.ctx.objectStats[path] = await self.objStat(path,
                                                            timeout=timeout)
            return self.ctx.objectStats[path]
        except aioipfs.APIError:
            self.ctx.objectStats[path] = None

    def objStatCtxGet(self, path):
        return self.ctx.objectStats.get(path, None)

    async def addPath(self, path, recursive=True, wrap=False,
                      callback=None, cidversion=1):
        """
        Add files from path in the repo, and returns the top-level entry (the
        root directory), optionally wrapping it with a directory object

        :param str path: the path to the directory/file to import
        :param bool wrap: add a wrapping directory
        :param bool recursive: recursive import
        :return: the IPFS top-level entry
        :rtype: dict
        """
        added = None
        try:
            async for entry in self.client.add(path, quiet=True,
                                               recursive=recursive,
                                               cid_version=cidversion,
                                               wrap_with_directory=wrap):
                await self.sleep()
                added = entry
                if asyncio.iscoroutinefunction(callback):
                    await callback(entry)
        except aioipfs.APIError as err:
            self.debug(err.message)
            return None
        except Exception as e:
            self.debug('addEntry: unknown exception {}'.format(str(e)))
            return None
        else:
            return added

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
            return json.loads(data)
        except aioipfs.APIError as err:
            self.debug(err.message)
            return None

    async def dagPut(self, data, pin=False):
        """
        Create a new DAG object from data and returns the root CID of the DAG
        """
        dagFile = tempfile.NamedTemporaryFile()
        if not dagFile:
            return None
        try:
            dagFile.write(json.dumps(data).encode())
        except Exception as e:
            self.debug('Cannot convert DAG object: {}'.format(str(e)))
            return None

        dagFile.seek(0, 0)
        try:
            output = await self.client.dag.put(dagFile.name, pin=pin)

            if 'Cid' in output:
                return output['Cid'].get('/', None)
            else:
                self.debug('dagPut: no CID in output')
                return None
        except aioipfs.APIError as err:
            self.debug(err.message)
            return None

    async def dagGet(self, dagPath, timeout=10):
        """
        Get the DAG object referenced by the DAG path and returns a JSON object
        """

        output = await self.waitFor(self.client.dag.get(dagPath), timeout)
        if output is not None:
            return json.loads(output)
        return None

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

    async def whoProvides(self, key, numproviders=20, timeout=20):
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
            await asyncio.wait_for(
                self.findProviders(key, peers, True,
                                   numproviders), timeout)
        except asyncio.TimeoutError:
            # It timed out ? Return what we got
            self.debug('whoProvides: timed out')
            return peers

        return peers

    @async_generator
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

            await yield_((pTime, pSuccess, pText.strip()))

    async def pingLowest(self, peer, count=3):
        """
        Return lowest ping latency for a peer

        :param str peer: Peer ID
        :param int count: ping count
        """

        lowest = 0
        async for time, success, text in self.pingWrapper(peer, count=count):
            if lowest == 0 and time != 0 and success is True:
                lowest = time
            if time > 0 and time < lowest and success is True:
                lowest = time
        return lowest

    async def pingAvg(self, peer, count=3):
        """
        Return average ping latency for a peer in msecs

        :param str peer: Peer ID
        :param int count: ping count
        :return: average latency in milliseconds or 0 if ping failed
        """

        received = []
        async for time, success, text in self.pingWrapper(peer, count=count):
            if time != 0 and success is True:
                received.append(time)

        if len(received) > 0:
            return float((sum(received) / len(received)) / 1000000)
        else:
            return 0

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

    async def hasDagCommand(self):
        return await self.hasCommand('dag')

    async def hasP2PCommand(self):
        return await self.hasCommand('p2p')


class IPFSOpRegistry:
    _registry = {}
    _key_default = 0

    @staticmethod
    def reg(key, inst):
        if key not in IPFSOpRegistry._registry:
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
