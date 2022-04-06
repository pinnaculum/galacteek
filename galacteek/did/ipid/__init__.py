import base64
import asyncio
import posixpath
import json
import re
import random
import string
import weakref

from rdflib import URIRef
from rdflib import RDF
from rdflib import Literal

from aiohttp.web_exceptions import HTTPOk
from datetime import datetime

from yarl import URL
from cachetools import LRUCache

from urllib.parse import urlencode

from galacteek import AsyncSignal
from galacteek import ensure
from galacteek import ensureLater
from galacteek import log
from galacteek import loopTime
from galacteek.core import SingletonDecorator
from galacteek.config import cGet

from galacteek.ipfs.wrappers import ipfsOp
from galacteek.ipfs.cidhelpers import cidValid
from galacteek.ipfs.cidhelpers import stripIpfs
from galacteek.ipfs.cidhelpers import joinIpns
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ipfs.dag import DAGOperations
from galacteek.ipfs.encrypt import IpfsRSAAgent
from galacteek.did import ipidIdentRe
from galacteek.did import didExplode
from galacteek.did import normedUtcDate
from galacteek.core import utcDatetimeIso
from galacteek.core import nonce
from galacteek.core import unusedTcpPort
from galacteek.core import runningApp
from galacteek.core.asynclib import async_enterable
from galacteek.core.asynccache import amlrucache
from galacteek.crypto.rsa import RSAExecutor

from galacteek.ld.signatures import jsonldsig
from galacteek.ld.rdf import BaseGraph
from galacteek.ld.rdf.terms import DID

from galacteek.did.ipid.services import IPService
from galacteek.did.ipid.services import IPServiceRegistry
from galacteek.did.ipid.services import IPServiceEditor
from galacteek.did.ipid.services import IPIDServiceException
from galacteek.did.ipid.services import passport  # noqa
from galacteek.did.ipid.services import gem  # noqa


def ipidFormatValid(did):
    return ipidIdentRe.match(did)


class IPIDException(Exception):
    pass


class IPIdentifier(DAGOperations):
    """
    InterPlanetary IDentifier (decentralized identity)

    This tries to follow the IPID spec as much as possible.
    """

    def __init__(self, did, localId=False, ldCache=None):
        self._did = did
        self._p2pServices = weakref.WeakValueDictionary()
        self._document = {}
        self._docCid = None
        self._localId = localId
        self._lastResolve = None
        self._latestModified = None
        self._unlocked = False
        self.rsaAgent = None

        # JSON-LD expanded cache
        self.cache = ldCache if ldCache else LRUCache(4)

        # Async sigs
        self.sChanged = AsyncSignal(str)
        self.sServicesChanged = AsyncSignal()
        self.sServiceAvailable = AsyncSignal(IPIdentifier, IPService)
        self.sChanged.connectTo(self.onDidChanged)

    @property
    def local(self):
        return self._localId is True

    @property
    def unlocked(self):
        return self._unlocked

    @property
    def dagCid(self):
        return self.docCid

    @property
    def dagIpfsPath(self):
        return IPFSPath(self.dagCid)

    @property
    def docCid(self):
        return self._docCid

    @docCid.setter
    def docCid(self, cid):
        self.message('Updating DIDDoc CID from {prev} to {n}'.format(
            prev=self._docCid, n=cid))

        if cidValid(cid):
            self._docCid = cid

    @property
    def doc(self):
        return self._document

    @property
    def did(self):
        return self._did

    @property
    def didUriRef(self):
        return URIRef(self._did)

    @property
    def p2pServices(self):
        return self._p2pServices

    @property
    def id(self):
        return self.ipnsKey

    @property
    def ipnsKey(self):
        exploded = didExplode(self.did)
        if exploded and exploded['method'] == 'ipid':
            return exploded['id']

    @property
    def latestModified(self):
        return self._latestModified

    def contextUrl(self, path, fragment=None):
        return str(
            URL.build(
                host='galacteek.ld',
                scheme='ips',
                path='/' + path,
                fragment=fragment
            )
        )

    def message(self, msg, level='debug'):
        getattr(log, level)('IPID ({loc}) ({did}): {msg}'.format(
            did=self.did, msg=msg, loc='local' if self._localId else 'net'))

    def didFragment(self, frag):
        return self.didUrl(fragment=frag)

    def didUrl(self, params=None, path=None,
               query=None, fragment=None):
        """
        Build a DID URL with the given params
        """

        url = '{did}'.format(did=self.did)

        if isinstance(params, dict):
            p = ['{0}={1}'.format(k, str(v)) for k, v in params.items()]
            url += ';' + ';'.join(p)

        if isinstance(path, str):
            # url += path
            if not path.startswith('/'):
                url += f'/{path}'
            else:
                url += path

        if isinstance(query, dict):
            url += '?' + urlencode(query)

        if isinstance(fragment, str):
            if not fragment.startswith('#'):
                url += '#' + fragment
            else:
                url += fragment

        return url

    def dump(self):
        """
        Dump the DID document to stdout
        """

        print(json.dumps(self.doc, indent=4))

    async def onDidChanged(self, cid):
        cacheKey = repr(self)
        if cacheKey in self.cache:
            # Reset expanded cache
            self.message('LRU cache reset')
            del self.cache[cacheKey]

    @ipfsOp
    async def rdfGraph(self, ipfsop):
        """
        Return the RDF graph for the DID document

        The documentIpfsCid predicate is always added
        """
        if self.doc:
            async with ipfsop.ldOps() as ld:
                g = await ld.rdfify(self.doc)

                g.add((
                    self.didUriRef,
                    DID.documentIpfsCid,
                    Literal(str(self.docCid))
                ))

            return g

    @ipfsOp
    async def unlock(self, ipfsop, rsaPassphrase=None):
        rsaAgent = await self.rsaAgentGet(ipfsop)
        if not rsaAgent:
            raise Exception('Agent')

        if await rsaAgent.privKeyUnlock(passphrase=rsaPassphrase):
            self._unlocked = True
        else:
            self._unlocked = False

        return self.unlocked

    async def rsaAgentGet(self, ipfsop):
        curProfile = ipfsop.ctx.currentProfile

        if self.rsaAgent:
            return self.rsaAgent

        if self.local:
            privKeyPath = curProfile._didKeyStore._privateKeyPathForDid(
                self.did)

            if not privKeyPath:
                raise Exception('Cannot find private DID key')

            pubKeyPem = await self.pubKeyPemGet(idx=0)

            self.rsaAgent = IpfsRSAAgent(
                ipfsop.ctx.rsaExec, pubKeyPem, privKeyPath)
            return self.rsaAgent

    @ipfsOp
    async def pssSign64(self, ipfsop, message: bytes):
        agent = await self.rsaAgentGet(ipfsop)
        if agent:
            return await agent.pssSign64(message)

    @ipfsOp
    async def pssVerif(self, ipfsop, message: bytes, signature: bytes):
        pubKeyPem = await self.pubKeyPemGet(idx=0)
        if pubKeyPem:
            return await ipfsop.ctx.rsaExec.pssVerif(
                message, signature, pubKeyPem)

    @ipfsOp
    async def inline(self, ipfsop, path=''):
        # In-line the JSON-LD contexts in the DAG for JSON-LD usage

        return await ipfsop.ldInline(await self.get(path=path))

    @ipfsOp
    async def compact(self, ipfsop):
        async with ipfsop.ldOps() as ld:
            return await ld.dagCompact(
                self.dagIpfsPath
            )

    @amlrucache
    async def expand(self):
        return await self._expand()

    @ipfsOp
    async def _expand(self, ipfsop, path=''):
        """
        Perform a JSON-LD expansion on the DID document
        """

        try:
            async with ipfsop.ldOps() as ld:
                expanded = await ld.dagExpandAggressive(
                    self.dagIpfsPath)

            if isinstance(expanded, list) and len(expanded) > 0:
                return expanded[0]
        except Exception as err:
            self.message('Error expanding DID document: {}'.format(
                str(err)))

    @ipfsOp
    async def expandService(self, ipfsop, srvId):
        try:
            expanded = await self.expand()
            if not expanded:
                return None

            for srv in expanded.get('https://w3id.org/did#service', []):
                if srv.get('@id') == srvId:
                    return srv
        except Exception:
            pass

    @ipfsOp
    async def compactService(self, ipfsop, srvId):
        """
        TODO: optimize, this is gonna be called often

        Caching is the lazy option
        """
        try:
            compact = await self.compact()

            for srv in compact['service']:
                if srv.get('id') == srvId:
                    return srv

            return None
        except Exception:
            pass

    async def update(self, obj: dict, publish=False):
        self._document.update(obj)
        await self.updateDocument(self.doc, publish=publish)

    async def flush(self):
        await self.updateDocument(self.doc, publish=True)

    async def servicePropagate(self, service: IPService):
        log.debug(f'Propagating IP service: {service}')

        await self.sServiceAvailable.emit(self, service)

    async def localServicesScan(self):
        if self.local:
            self.message('Scanning local DID services')

            # Local IPID: propagate did services
            async for service in self.discoverServices():
                await self.sServiceAvailable.emit(self, service)

    async def addServiceRaw(self, service: dict, publish=True):
        sid = service.get('id')
        assert isinstance(sid, str)

        didEx = didExplode(sid)
        assert didEx is not None

        if await self.searchServiceById(sid) is not None:
            raise IPIDServiceException(
                'An IP service already exists with this ID')

        self._document['service'].append(service)
        await self.updateDocument(self.doc, publish=publish)
        await self.sServicesChanged.emit()

        sInst = self._serviceInst(service)
        await self.servicePropagate(sInst)

        return sInst

    @ipfsOp
    async def addServiceContexted(self, ipfsop, service: dict,
                                  endpoint=None,
                                  publish=True,
                                  contextInline=False,
                                  context='IpfsObjectEndpoint'):
        sid = service.get('id')
        assert isinstance(sid, str)

        didEx = didExplode(sid)
        assert didEx is not None

        if await self.searchServiceById(sid) is not None:
            raise IPIDServiceException(
                'An IP service already exists with this ID')

        if contextInline is True:
            service['serviceEndpoint'] = {
                '@context': await ipfsop.ldContext(context)
            }
        else:
            service['serviceEndpoint'] = {
                '@context': f'ips://galacteek.ld/{context}',
                '@type': context
            }

        if isinstance(endpoint, dict):
            service['serviceEndpoint'].update(endpoint)

        self._document['service'].append(service)
        await self.updateDocument(self.doc, publish=publish)
        await self.sServicesChanged.emit()

        sInst = self._serviceInst(service)
        await self.servicePropagate(sInst)

        return sInst

    @ipfsOp
    async def addServiceCollection(self, ipfsop, name):
        return await self.addServiceContexted({
            'id': self.didUrl(
                path=posixpath.join('/collections', name)
            ),
            'type': IPService.SRV_TYPE_COLLECTION,
        }, context='ObjectsCollectionEndpoint',
            endpoint={
            '@id': self.didUrl(
                path=posixpath.join('/collections', name),
                fragment='#endpoint'
            ),
            'name': name,
            'created': utcDatetimeIso(),
            'objects': []
        }, publish=True)

    @ipfsOp
    async def addServiceRendezVous(self, ipfsop):
        serviceName = 'ps-rendezvous'
        return await self.addServiceRaw({
            'id': self.didUrl(
                path=f'/{serviceName}'
            ),
            'type': IPService.SRV_TYPE_PSRENDEZVOUS,
            'description': 'PubSub rendezvous',
            'serviceEndpoint': ipfsop.p2pEndpoint(serviceName)
        })

    @ipfsOp
    async def addServiceVideoCall(self, ipfsop, roomName):
        servicePath = posixpath.join('videocall', roomName)

        return await self.addServiceContexted({
            'id': self.didUrl(
                path=servicePath
            ),
            'type': IPService.SRV_TYPE_VIDEOCALL,
        }, context='DwebVideoCallServiceEndpoint',
            endpoint={
            'roomName': roomName,
            'created': utcDatetimeIso(),
            'p2pEndpoint': ipfsop.p2pEndpoint(servicePath)
        }, publish=True)

    @ipfsOp
    async def updateDocument(self, ipfsop, document, publish=False):
        """
        Update the DID document
        """

        now = normedUtcDate()
        self._document = document

        if self.docCid:
            # 'previous'
            if 'previous' in self._document:
                del self._document['previous']

            if 0:
                self._document['previous'] = {
                    '/': self.docCid
                }

        self._document['updated'] = now

        cid = await ipfsop.dagPut(document)

        if cid:
            self.docCid = cid

            if publish:
                ensure(self.publish())

            await self.sChanged.emit(cid)

            # await self.rdfPush()
        else:
            self.message('Could not inject new DID document!')

    async def rdfPush(self):
        # Push that to the RDF store
        await runningApp().s.rdfStore(IPFSPath(self.docCid))

    @ipfsOp
    async def jsonLdSign(self, ipfsop, document: dict):
        """
        Create a JSON-LD signature for an object, signed with
        the DID's key
        """
        try:
            rsaAgent = await self.rsaAgentGet(ipfsop)
            privKey = await rsaAgent._privateKey()

            return jsonldsig.sign(document, privKey.exportKey())
        except Exception as err:
            self.message(f'Failed to create JSON-LD signature: {err}')

    @ipfsOp
    async def jsonLdSigVerify(self, ipfsop, document, pubKey=None):
        try:
            rsaAgent = await self.rsaAgentGet(ipfsop)

            return jsonldsig.verify(
                document, pubKey if pubKey else rsaAgent.pubKeyPem
            )
        except Exception as err:
            self.message(f'Failed to verify JSON-LD signature: {err}')

    @ipfsOp
    async def jsonLdSubjectSignature(self, ipfsop, uri):
        """
        Return a subjectSignature
        """
        try:
            rsaAgent = await self.rsaAgentGet(ipfsop)

            token = await rsaAgent.jwsToken(str(uri))
            jwss = token.serialize(compact=True)

            return {
                'type': 'RsaSignature2018',
                'creator': str(self.didUriRef),
                'created': datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
                'signatureValue': jwss
            }
        except Exception as err:
            self.message(f'Failed to create signature: {err}')

    @ipfsOp
    async def jsonLdSubjectSigVerify(self, ipfsop,
                                     signature: str,
                                     subjUri: URIRef,
                                     pubKeyPem: str):
        """
        Verify a subjectSignature
        """
        try:
            rsaAgent = await self.rsaAgentGet(ipfsop)

            payload = await rsaAgent.rsaExec.jwsVerifyFromPem(
                signature, pubKeyPem
            )

            return payload.decode('utf-8') == str(subjUri)
        except Exception as err:
            self.message(f'Failed to create signature: {err}')

    @ipfsOp
    async def resolve(self, ipfsop, resolveTimeout=None):
        resolveTimeout = resolveTimeout if resolveTimeout else \
            cGet('resolve.timeout')

        if self.local:
            maxLifetime = cGet('resolve.cacheLifetime.local.seconds')
        else:
            maxLifetime = cGet('resolve.cacheLifetime.default.seconds')

        useCache = 'always'
        cache = 'always'

        self.message('DID resolve: {did} (using cache: {usecache})'.format(
            did=self.ipnsKey, usecache=useCache))

        return await ipfsop.nameResolve(
            joinIpns(self.ipnsKey),
            timeout=resolveTimeout,
            useCache=useCache,
            cache=cache,
            cacheOrigin='ipidmanager',
            maxCacheLifetime=maxLifetime
        )

    async def refresh(self):
        staleValue = cGet('resolve.staleDelay')
        last = self._lastResolve

        if self.local or not last or (loopTime() - last) > staleValue:
            self.message('Reloading')

            return await self.load()

    @ipfsOp
    async def load(self, ipfsop, pin=True, initialCid=None,
                   resolveTimeout=30):
        if not initialCid:
            resolved = await self.resolve()

            if not resolved:
                self.message('Failed to resolve ?')
                return False

            dagCid = stripIpfs(resolved['Path'])
        else:
            self.message('Loading from initial CID: {}'.format(initialCid))
            dagCid = initialCid

        self.message('DID resolves to {}'.format(dagCid))

        if self.docCid == dagCid:
            # We already have this one

            self.message('DID document already at latest iteration')
            return False

        self._lastResolve = loopTime()

        if pin is True:
            await ipfsop.ctx.pin(dagCid, qname='ipid')

        self.message('Load: IPNS key resolved to {}'.format(dagCid))

        doc = await ipfsop.dagGet(dagCid)

        if doc:
            self._document = doc
            self._latestModified = doc.get('modified')
            self.docCid = dagCid
            await self.sChanged.emit(dagCid)

            await self.localServicesScan()

            # Graph it
            # await self.rdfPush()

            return True

        return False

    @ipfsOp
    async def publish(self, ipfsop, timeout=None):
        """
        Publish the DID document to the IPNS key

        We always cache the record so that your DID is always
        resolvable whatever the connection state.

        :rtype: bool
        """

        # Get config settings
        timeout = timeout if timeout else cGet('publish.ipns.timeout')
        autoRepublish = cGet('publish.autoRepublish')
        republishDelay = cGet('publish.autoRepublishDelay')

        ipnsLifetime = cGet('publish.ipns.lifetime')
        ipnsTtl = cGet('publish.ipns.ttl')

        if not self.docCid:
            return False

        if autoRepublish is True:
            # Auto republish for local IPIDs
            ensureLater(
                republishDelay,
                self.publish
            )

        try:
            if await ipfsop.publish(self.docCid,
                                    key=self.ipnsKey,
                                    lifetime=ipnsLifetime,
                                    ttl=ipnsTtl,
                                    cache='always',
                                    cacheOrigin='ipidmanager',
                                    timeout=timeout):
                self.message('Published !')
                self.message(
                    'Published IPID {did} with docCid: {docCid}'.format(
                        did=self.did, docCid=self.docCid))
                return True
            else:
                self.message('Error publishing IPID with DID: {did}'.format(
                    did=self.did))
                return False
        except Exception as e:
            self.message(str(e))
            return False

    @ipfsOp
    async def dagGet(self, ipfsop, path):
        if self.docCid:
            dPath = posixpath.join(self.docCid, path)
            self.message('DID docget: {}'.format(dPath))

            try:
                return await ipfsop.dagGet(dPath)
            except Exception as err:
                self.message('DAG get error for {p}: {err}'.format(
                    p=dPath, err=str(err)))
        else:
            self.message('DAG get impossible (no DID document yet)')

    async def pubKeys(self):
        """
        Async generator that yields each publicKey
        """
        for pKey in await self.dagGet('publicKey'):
            yield pKey

    async def pubKeyWithId(self, id: str):
        """
        Get first publicKey that matches the id

        :param str id: PublicKey id
        """

        async for pKey in self.pubKeys():
            if pKey.get('id') == id:
                return pKey

    async def pubKeyGet(self, idx=0):
        """
        Returns the publicKey node with the idx index in the array

        :param int idx: Public key index
        :rtype: dict
        """
        return await self.dagGet('publicKey/{}'.format(idx))

    async def pubKeyPemGet(self, idx=0):
        """
        Returns the publicKey PEM with the idx index in the array

        :rtype: str
        """
        return await self.dagGet('publicKey/{}/publicKeyPem'.format(idx))

    async def pubKeyPemGetWithId(self, keyId):
        """
        Returns the publicKey PEM whose id matches keyId

        :rtype: str
        """

        for key in await self.dagGet('publicKey'):
            if key.get('id') == keyId:
                return key['publicKeyPem']

    async def getServices(self):
        node = await self.dagGet('service')
        return node if node else []

    def _serviceInst(self, srv):
        stype = srv.get('type')

        for cname, sclass in IPServiceRegistry.IPSREGISTRY.items():
            if stype in sclass.forTypes:
                return sclass(srv, self)

    async def discoverServices(self):
        for srv in await self.getServices():
            _inst = self._serviceInst(srv)
            if _inst:
                yield _inst

    async def getServiceByType(self, srvType: str):
        """
        Get first service found that matches the service type

        :param str srvType: Service type
        """

        for srv in await self.getServices():
            if srv.get('type') == srvType:
                return IPService(srv, self)

    async def searchServices(self, query: str):
        for srvNode in await self.getServices():
            service = IPService(srvNode, self)

            if re.search(query, service.id, re.IGNORECASE):
                yield service

    async def searchServiceById(self, _id: str):
        for srvNode in await self.getServices():
            if srvNode['id'] == _id:
                _inst = self._serviceInst(srvNode)
                if _inst:
                    return _inst

            await asyncio.sleep(0)

    async def removeServiceById(self, _id: str):
        """
        Remove the service with the given DID identifier
        """
        try:
            for srv in self._document['service']:
                if srv['id'] == _id:
                    sInst = self._serviceInst(srv)
                    if sInst:
                        await sInst.serviceStop()

                    self._document['service'].remove(srv)
                    await self.flush()
        except Exception as err:
            log.debug(str(err))

    async def avatarService(self):
        avatarServiceId = self.didUrl(path='/avatar')
        return await self.searchServiceById(avatarServiceId)

    async def avatarSet(self, ipfsPath: IPFSPath):
        avatarServiceId = self.didUrl(path='/avatar')

        if not await self.avatarService():
            await self.addServiceRaw({
                'id': avatarServiceId,
                'type': IPService.SRV_TYPE_AVATAR,
                'serviceEndpoint': ipfsPath.ipfsUrl,
                'description': 'User Avatar'
            }, publish=True)
        else:
            async with self.editServiceById(avatarServiceId) as editor:
                editor.service['serviceEndpoint'] = ipfsPath.ipfsUrl

    @async_enterable
    async def editServiceById(self, _id: str, sync=True):
        """
        Edit the IP service with the given ID

        Returns an async context which flushes the DID document
        by default on leaving the context
        """
        for srv in self._document['service']:
            if srv['id'] == _id:
                return IPServiceEditor(self, srv, sync=sync)

    async def _stopP2PServices(self):
        for srvName, srv in self._p2pServices.items():
            await srv.stop()

    async def _stop(self):
        await self._stopP2PServices()

    async def upgrade(self):
        if not self.local:
            return

        ps = await self.searchServiceById(
            self.didUrl(path='/passport'))

        if not ps:
            # Create a dweb passport
            await passport.create(self)

    def __eq__(self, other):
        return self.did == other.did

    def __repr__(self):
        return self.did

    def __str__(self):
        return 'IP Identifier: {did}'.format(did=self.did)


@SingletonDecorator
class IPIDManager:
    def __init__(self):
        self._managedIdentifiers = {}
        self._lock = asyncio.Lock()
        self._resolveTimeout = cGet('resolve.timeout')
        self._rsaExec = RSAExecutor()

        # JSON-LD cache
        self._ldCache = LRUCache(256)

    async def stopManager(self):
        async with self._lock:
            for didIdentifier, ipid in self._managedIdentifiers.items():
                if ipid.local:
                    log.debug(f'Stopping DID: {didIdentifier}')
                    await ipid._stop()

    async def onLocalIpidServiceAvailable(self, ipid, ipService):
        log.debug(f'{ipid.did}: Starting IPID service: {ipService}')

        try:
            periodic = getattr(ipService, 'periodicTask')
            if asyncio.iscoroutinefunction(periodic):
                ensure(periodic())
        except Exception:
            pass

        await ipService.serviceStart()

    async def track(self, ipid: IPIdentifier):
        async with self._lock:
            self._managedIdentifiers[ipid.did] = ipid

    async def searchServices(self, term: str):
        async with self._lock:
            for did, ipid in self._managedIdentifiers.items():
                async for srv in ipid.searchServices(term):
                    yield srv

                await asyncio.sleep(0)

    async def getServiceById(self, _id: str):
        async with self._lock:
            for did, ipid in self._managedIdentifiers.items():
                srv = await ipid.searchServiceById(_id)
                if srv:
                    return srv

                await asyncio.sleep(0)

    async def trackingTask(self):
        while True:
            await asyncio.sleep(60 * 5)

            async with self._lock:
                for did, ipId in self._managedIdentifiers.items():
                    await ipId.load()
                    log.debug('tracker: {0} => {1}'.format(
                        ipId, ipId.docCid))

    @ipfsOp
    async def load(self, ipfsop,
                   did: str,
                   timeout=None,
                   localIdentifier=False,
                   initialCid=None,
                   track=True):

        if not did or not ipidFormatValid(did):
            return None

        async with self._lock:
            if did in self._managedIdentifiers:
                return self._managedIdentifiers[did]

        rTimeout = timeout if timeout else self._resolveTimeout

        ipid = IPIdentifier(
            did, localId=localIdentifier, ldCache=self._ldCache)

        if ipid.local:
            ipid.sServiceAvailable.connectTo(
                self.onLocalIpidServiceAvailable)

        if await ipid.load(resolveTimeout=rTimeout, initialCid=initialCid):
            if track:
                await self.track(ipid)

            if localIdentifier:
                log.debug('Publishing (first load) local IPID: {}'.format(did))
                ensure(ipid.publish())

            return ipid

    @ipfsOp
    async def create(self, ipfsop,
                     ipnsKeyName: str,
                     pubKeyPem=None,
                     purgeKey=True,
                     track=True):
        """
        Create a DID with the IPID method

        :param str ipnsKeyName: IPNS key name to use
        :param str pubKeyPem: RSA PubKey PEM
        :param bool purgeKey: Remove IPNS key if it already exists
        """
        names = await ipfsop.keysNames()

        if ipnsKeyName in names and purgeKey:
            await ipfsop.keysRemove(ipnsKeyName)

        ipnsKey = await ipfsop.keyGen(ipnsKeyName)
        if ipnsKey is None:
            raise IPIDException('Cannot create IPNS Key')

        ipnsKeyId = ipnsKey['Id']

        didId = "did:ipid:{key}".format(key=ipnsKeyId)

        log.debug('Generating DID document with DID: {}'.format(didId))

        now = normedUtcDate()

        identifier = IPIdentifier(didId, localId=True)

        # Initial document
        initialDoc = {
            "@context": {
                "@vocab": "ips://galacteek.ld/"
            },
            "@type": "did",
            "publicKey": [{
                "id": "{did}#keys-1".format(did=didId),
                "type": "RsaVerificationKey2018",
                "controller": didId,
                "publicKeyPem": pubKeyPem
            }],
            "service": [],
            "created": now,
            "updated": now
        }

        await identifier.updateDocument(initialDoc)

        # Update the document with the IPID and auth section
        await identifier.update({
            'id': didId,
            "authentication": [{
                "id": "{did}#keys-1".format(did=didId),
                "type": "RsaSignatureAuthentication2018",
                "controller": didId,
                "publicKey": [
                    didId
                ]
            }]
        })

        # Publish the DID document to the key
        ensure(identifier.publish())

        if track:
            await self.track(identifier)

        # Register default IP services
        # for service in ipfsop.ctx.p2p.services:
        #     if service.didDefaultRegister:
        #         await service.didServiceInstall(identifier)

        return identifier

    @ipfsOp
    async def didAuthenticate(self, ipfsop, ipid: IPIdentifier, peerId,
                              token=None):
        log.debug('DID auth for {}'.format(ipid))
        lPort = unusedTcpPort()

        if not lPort:
            return

        async with ipfsop.p2pDialer(
                peerId, 'didauth-vc-pss',
                addressAuto=True) as streamCtx:
            if streamCtx.failed:
                return False
            else:
                log.debug(
                    f'DID Authenticate ({ipid.did}): connected to service')
                await ipfsop.sleep(0.5)

                return await self.didAuthPerform(
                    ipfsop, streamCtx, ipid, token=token)

    async def didAuthPerform(self, ipfsop, streamCtx, ipid, token=None):
        rand = random.Random()
        req = {
            'challenge': ''.join(
                [str(rand.choice(string.ascii_letters)) for x in range(
                    0, rand.randint(256, 384))]),
            'did': ipid.did,
            'nonce': nonce()
        }

        if token:
            req['ident_token'] = token

        try:
            async with streamCtx.session as session:
                async with session.post(
                        streamCtx.httpUrl('/auth'),
                        data=json.dumps(req)) as resp:
                    if resp.status != HTTPOk.status_code:
                        payload = await resp.json()
                        log.debug(f'Error payload: {payload}')
                        raise Exception(f'DID Auth error: code {resp.status}')

                    payload = await resp.json()

                    # Expand the response and verify it

                    async with ipfsop.ldOps() as ldCtx:
                        expanded = await ldCtx.expandDocument(payload)
                        if not expanded:
                            raise Exception('Invalid IPLD document')

                    return await self.vcLdValidate(
                        ipid, req, expanded
                    )
        except Exception as err:
            log.debug(f'didAuthPerform error: {err}')
            return False

    @ipfsOp
    async def vcLdValidate(self, ipfsop, ipid, req, document):
        """ Validate the verifiable credentials """

        try:
            # vcid = URIRef('urn:glk:vc:{did}'.format(did=req['did']))
            # sigid = URIRef('urn:glk:vc:{did}:proof'.format(did=req['did']))

            graph = BaseGraph().parse(
                data=json.dumps(document), format='json-ld'
            )
            assert graph is not None

            vcid = graph.value(
                predicate=RDF.type,
                object=URIRef(
                    'https://www.w3.org/2018/credentials#VerifiableCredential'
                )
            )
            sigid = graph.value(
                predicate=RDF.type,
                object=URIRef(
                    'https://w3id.org/security#RsaSignature2018'
                )
            )

            issued = graph.value(
                subject=vcid,
                predicate=URIRef('https://www.w3.org/2018/credentials#issued')
            )

            assert issued is not None

            # Issuer's DID

            issuer = graph.value(
                subject=vcid,
                predicate=URIRef('https://www.w3.org/2018/credentials#issuer')
            )
            issuer = document.get(
                'https://www.w3.org/2018/credentials#issuer')[0]['@id']
            assert issuer == req['did']

            # Credential Subject
            cSubject = graph.value(
                subject=vcid,
                predicate=URIRef(
                    'https://www.w3.org/2018/credentials#credentialSubject'
                )
            )

            assert str(cSubject) == req['did']

            # Get the proof and check the type and nonce

            challenge = graph.value(
                subject=sigid,
                predicate=URIRef('https://w3id.org/security#challenge')
            )
            assert str(challenge) == req['nonce']

            purpose = graph.value(
                subject=sigid,
                predicate=URIRef('https://w3id.org/security#proofPurpose')
            )

            assert purpose == URIRef(
                'https://w3id.org/security#authenticationMethod'
            )

            sigValue = graph.value(
                subject=sigid,
                predicate=URIRef('https://w3id.org/security#proofValue')
            )

            # IRI: https://w3id.org/security#verificationMethod
            # corresponds to the signer's publicKey DID's id
            vMethod = graph.value(
                subject=sigid,
                predicate=URIRef(
                    'https://w3id.org/security#verificationMethod'
                )
            )

            assert sigValue is not None
            assert vMethod is not None

            rsaPubPem = await ipid.pubKeyPemGetWithId(str(vMethod))
            if not rsaPubPem:
                log.debug('didAuthPerform: PubKey not found: {}'.format(
                    str(vMethod)))
                return False

            # Check the signature with PSS
            return await self._rsaExec.pssVerif(
                req['challenge'].encode(),
                base64.b64decode(str(sigValue)),
                rsaPubPem
            )
        except AssertionError as aerr:
            log.debug(f'Verifiable credentials assert error: {aerr}')
            return False
        except Exception as err:
            log.debug(f'Unknown VC error: {err}')
            return False
