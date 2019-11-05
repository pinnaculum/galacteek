import asyncio
import os.path
import json
import re
from urllib.parse import urlencode

from galacteek import AsyncSignal
from galacteek.ipfs.wrappers import ipfsOp
from galacteek.ipfs.cidhelpers import stripIpfs
from galacteek.ipfs.cidhelpers import joinIpns
from galacteek.did import ipidIdentRe
from galacteek.did import didExplode
from galacteek.did import normedUtcDate

from galacteek import log


didSpecPath = os.path.join(
    os.path.dirname(__file__), 'contexts', 'did-v1.jsonld')


def ipidFormatValid(did):
    return ipidIdentRe.match(did)


class IPIDException(Exception):
    pass


class IPIDServiceException(Exception):
    pass


class IPService:
    """
    InterPlanetary Service (attached to an IPID)
    """

    # Service constants

    SRV_TYPE_DWEBBLOG = 'DwebBlogService'
    SRV_TYPE_GALLERY = 'DwebGalleryService'
    SRV_TYPE_VC = 'VerifiableCredentialService'
    SRV_TYPE_GENERICPYRAMID = 'GalacteekPyramidService'

    def __init__(self, dagNode: dict):
        self._srv = dagNode
        self._didEx = didExplode(self.id)

    @property
    def id(self):
        return self._srv['id']

    @property
    def description(self):
        return self._srv.get('description', 'No description')

    @property
    def pubdate(self):
        return self._srv.get('datepublished')

    @property
    def srvIpId(self):
        return self._didEx['id'] if self._didEx else None

    @property
    def srvFragment(self):
        return self._didEx['fragment'] if self._didEx else None

    @property
    def srvPath(self):
        return self._didEx['path'] if self._didEx else None

    @property
    def type(self):
        return self._srv['type']

    @property
    def endpoint(self):
        return self._srv['serviceEndpoint']

    def __str__(self):
        if self.type == self.SRV_TYPE_DWEBBLOG:
            srvStr = 'User blog'
        elif self.type == self.SRV_TYPE_GALLERY:
            srvStr = 'Image gallery'
        elif self.typr == self.SRV_TYPE_GENERICPYRAMID:
            srvStr = 'Generic pyramid'
        else:
            srvStr = 'Unknown service'

        return 'IP Service: {srv}'.format(
            srv=srvStr
        )


class IPIdentifier:
    """
    InterPlanetary IDentifier (decentralized identity)

    This tries to follow the IPID spec as much as possible.
    """

    def __init__(self, did, localId=False):
        self._did = did
        self._document = {}
        self._docCid = None
        self._localId = localId

        # Async sigs
        self.sChanged = AsyncSignal(str)

    @property
    def docCid(self):
        return self._docCid

    @docCid.setter
    def docCid(self, cid):
        self.message('Updating DIDDoc CID from {prev} to {n}'.format(
            prev=self._docCid, n=cid))
        self._docCid = cid

    @property
    def doc(self):
        return self._document

    @property
    def did(self):
        return self._did

    @property
    def id(self):
        return self.ipnsKey

    @property
    def ipnsKey(self):
        exploded = didExplode(self.did)
        if exploded and exploded['method'] == 'ipid':
            return exploded['id']

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

    async def update(self, obj: dict, publish=False):
        self._document.update(obj)
        await self.updateDocument(self.doc, publish=publish)

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

    @ipfsOp
    async def updateDocument(self, ipfsop, document, publish=False):
        """
        Update the document and set the 'previous' IPLD link
        """

        now = normedUtcDate()
        self._document = document

        if self.docCid:
            self._document['previous'] = {
                '/': self.docCid
            }

        self._document['updated'] = now

        cid = await ipfsop.dagPut(document)

        if cid:
            self.docCid = cid

            if publish:
                await self.publish()

            await self.sChanged.emit(cid)
        else:
            self.message('Could not inject new DID document!')

    @ipfsOp
    async def resolve(self, ipfsop, resolveTimeout=30):
        useCache = 'always' if self._localId else 'offline'

        return await ipfsop.nameResolve(
            joinIpns(self.ipnsKey),
            timeout=resolveTimeout,
            useCache=useCache,
            maxCacheLifetime=60 * 60 * 5
        )

    async def refresh(self):
        await self.load()

    @ipfsOp
    async def load(self, ipfsop, pin=True, resolveTimeout=30):
        resolved = await self.resolve(resolveTimeout=resolveTimeout)

        if not resolved:
            self.message('Failed to resolve ?')
            return False

        dagCid = stripIpfs(resolved['Path'])

        self.message('DID resolves to {}'.format(dagCid))

        if self.docCid == dagCid:
            # We already have this one

            self.message('DID document already at latest iteration')
            return False

        if pin is True:
            await ipfsop.pin(resolved['Path'])

        self.message('Load: IPNS key resolved to {}'.format(dagCid))

        doc = await ipfsop.dagGet(dagCid)

        if doc:
            self._document = doc
            self.docCid = dagCid
            return True

        return False

    @ipfsOp
    async def publish(self, ipfsop, timeout=30):
        """
        Publish the DID document to the IPNS key

        We always cache the record so that your DID is always
        resolvable whatever the connection state.

        :rtype: bool
        """

        if not self.docCid:
            return False

        try:
            if await ipfsop.publish(self.docCid,
                                    key=self.ipnsKey,
                                    lifetime='96h',
                                    allow_offline=True,
                                    cache='always',
                                    cacheOrigin='ipidmanager',
                                    timeout=timeout):
                self.message(
                    'Published IPID with DID docCid: {docCid}'.format(
                        docCid=self.docCid), level='info')
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
            dPath = os.path.join(self.docCid, path)
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

    async def getServices(self):
        return await self.dagGet('service')

    async def getServiceByType(self, srvType: str):
        """
        Get first service found that matches the service type

        :param str srvType: Service type
        """

        for srv in await self.getServices():
            if srv.get('type') == srvType:
                return IPService(srv)

    async def searchServices(self, query: str):
        for srvNode in await self.getServices():
            service = IPService(srvNode)

            if re.search(query, service.id, re.IGNORECASE):
                yield service

    async def searchServiceById(self, _id: str):
        for srvNode in await self.getServices():
            service = IPService(srvNode)

            if service.id == _id:
                return service

    def __eq__(self, other):
        return self.did == other.did

    def __str__(self):
        return 'IP Identifier: {did}'.format(did=self.did)


class IPIDManager:
    def __init__(self):
        self._managedIdentifiers = {}
        self._lock = asyncio.Lock()

    async def track(self, ipid: IPIdentifier):
        with await self._lock:
            self._managedIdentifiers[ipid.did] = ipid

    async def searchServices(self, term: str):
        with await self._lock:
            for did, ipid in self._managedIdentifiers.items():
                async for srv in ipid.searchServices(term):
                    yield srv

    async def trackingTask(self):
        while True:
            await asyncio.sleep(60 * 5)

            with await self._lock:
                for ipId in self._managedIdentifiers:
                    await ipId.load()

    @ipfsOp
    async def load(self, ipfsop,
                   did: str,
                   timeout=30,
                   localIdentifier=False,
                   track=True):
        if not ipidFormatValid(did):
            return None

        with await self._lock:
            if did in self._managedIdentifiers:
                return self._managedIdentifiers[did]

        ipid = IPIdentifier(did, localId=localIdentifier)
        if await ipid.load(resolveTimeout=timeout):
            if track:
                await self.track(ipid)

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
                "/":
                "bafkreiewxn2t3qadfxabcnne3av4hj7vhlxus2rtl7eh3gfrmnozi7vn6u"
            },
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
        await identifier.publish()

        if track:
            await self.track(identifier)

        return identifier
