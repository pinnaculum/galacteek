import time
from yarl import URL

from galacteek import AsyncSignal
from galacteek import log
from galacteek.core import runningApp

from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ipfs.wrappers import ipfsOp

from galacteek.ld.jsonldexpand import ExpandedJSONLDQuerier

from galacteek.did import didExplode


class IPIDServiceException(Exception):
    pass


class IPServiceRegistry(type):
    IPSREGISTRY = {}

    def __new__(cls, name, bases, attrs):
        new_cls = type.__new__(cls, name, bases, attrs)
        cls.IPSREGISTRY[new_cls.__name__] = new_cls
        return new_cls

    @classmethod
    def get_registry(cls):
        return dict(cls.IPSREGISTRY)


class IPServiceEditor(object):
    def __init__(self, ipid, service, sync=True):
        self.ipid = ipid
        self.service = service
        self.sync = sync

    async def __aenter__(self):
        log.debug('Editing Service: {}'.format(self.service.get('id')))
        return self

    async def __aexit__(self, *args):
        if self.sync is True:
            await self.ipid.flush()

        await self.ipid.sServicesChanged.emit()


class IPService(metaclass=IPServiceRegistry):
    """
    InterPlanetary Service (attached to an IPID)
    """

    # Service constants

    SRV_TYPE_DWEBBLOG = 'DwebBlogService'
    SRV_TYPE_DWEBSITE_GENERIC = 'GenericDwebSiteService'
    SRV_TYPE_GALLERY = 'DwebGalleryService'
    SRV_TYPE_ATOMFEED = 'DwebAtomFeedService'
    SRV_TYPE_AVATAR = 'DwebAvatarService'

    SRV_TYPE_PASSPORT = 'DwebPassportService'

    SRV_TYPE_VC = 'VerifiableCredentialService'
    SRV_TYPE_GENERICPYRAMID = 'GalacteekPyramidService'
    SRV_TYPE_CHAT = 'GalacteekChatService'
    SRV_TYPE_PSRENDEZVOUS = 'PSRendezVousService'
    SRV_TYPE_VIDEOCALL = 'DwebVideoCallService'

    SRV_TYPE_LIVEPEER_STREAMING = 'P2PLivePeerStreamingService'

    SRV_TYPE_COLLECTION = 'ObjectsCollectionService'

    SRV_TYPE_GEMINI_CAPSULE = 'GeminiIpfsCapsuleService'

    SRV_TYPE_HTTP_SERVICE = 'HttpWebsiteService'
    SRV_TYPE_HTTP_FORWARD_SERVICE = 'HttpForwardWebsiteService'

    forTypes = []
    container = False

    def __init__(self, dagNode: dict, ipid):
        self._srv = dagNode
        self._didEx = didExplode(self.id)
        self._ipid = ipid  # TODO: get rid of the ref
        self._p2pServices = []

        self.sChanged = AsyncSignal()
        self.sChanged.connectTo(self.onChanged)

    @property
    def ipid(self):
        return self._ipid

    @property
    def ipidServiceUrl(self):
        try:
            return URL.build(
                scheme='ipid',
                host=self.srvIpId,
                path=self.srvPath,
                fragment=self.srvFragment
            )
        except Exception:
            return None

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

    async def compact(self):
        return await self.ipid.compactService(self.id)

    async def expandEndpoint(self):
        exSrv = await self.ipid.expandService(self.id)
        if not exSrv:
            return None

        try:
            return exSrv.get('https://w3id.org/did#serviceEndpoint')[0]
        except Exception:
            return None

    async def expandEndpointLdWizard(self):
        return ExpandedJSONLDQuerier(
            await self.expandEndpoint())

    @ipfsOp
    async def endpointCat(self, ipfsop):
        ipfsPath = IPFSPath(self.endpoint)
        if ipfsPath.valid:
            return await ipfsop.catObject(ipfsPath.objPath)

    async def onChanged(self):
        pass

    async def serviceStart(self):
        pass

    async def serviceStop(self):
        for p2ps in self._p2pServices:
            await p2ps.stop()

    async def p2pServiceRegister(self, service):
        await (runningApp()).s.ipfsP2PService(service)

        self._p2pServices.append(service)

    async def pubsubServiceRegister(self, service):
        await (runningApp()).s.ipfsPubsubService(service)
        await service.startListening()

    async def request(self, command='PATCH', **kw):
        raise Exception(f'Unauthorized service request: {command}')

    def __repr__(self):
        return self.id

    def __str__(self):
        if self.type == self.SRV_TYPE_DWEBBLOG:
            srvStr = 'User blog'
        elif self.type == self.SRV_TYPE_GALLERY:
            srvStr = 'Image gallery'
        elif self.type == self.SRV_TYPE_GENERICPYRAMID:
            srvStr = 'Generic pyramid'
        elif self.type == self.SRV_TYPE_ATOMFEED:
            srvStr = 'Atom feed'
        elif self.type == self.SRV_TYPE_AVATAR:
            srvStr = 'User avatar'
        else:
            srvStr = 'Unknown service'

        return 'IPS: {srv}'.format(
            srv=srvStr
        )


class IPGenericService(IPService):
    forTypes = [
        IPService.SRV_TYPE_ATOMFEED,
        IPService.SRV_TYPE_DWEBBLOG,
        IPService.SRV_TYPE_DWEBSITE_GENERIC,
        IPService.SRV_TYPE_GALLERY,
        IPService.SRV_TYPE_GENERICPYRAMID,
        IPService.SRV_TYPE_AVATAR
    ]


class CollectionService(IPService):
    forTypes = ['ObjectsCollectionService']
    endpointName = 'ObjectsCollectionEndpoint'
    container = True

    async def getObjectWithId(self, id: str):
        async for obj in self.contained():
            if obj['id'] == id:
                return obj

    async def contained(self):
        endpoint = await self.expandEndpoint()
        if not endpoint:
            return

        try:
            for obj in endpoint.get(self.ipid.contextUrl(
                    self.endpointName, fragment='objects')):
                if '@id' not in obj:
                    continue

                yield {
                    'id': obj['@id'],
                    'path': obj.get(
                        self.ipid.contextUrl(
                            'IpfsObject', fragment='path')
                    )[0]['@value'],
                    'name': obj.get(
                        self.ipid.contextUrl(
                            'IpfsObject', fragment='name')
                    )[0]['@value']
                }
        except Exception as err:
            log.debug(f'Contained objects listing error: {err}')

    @ipfsOp
    async def add(self, ipfsop, objPath, name=None,
                  description='No description'):
        path = IPFSPath(objPath, autoCidConv=True)
        if not path.valid:
            raise ValueError('Invalid path')

        if not path.isRoot:
            oName = path.basename
        else:
            oName = name if name else hex(int(time.time() * 10000))[2:]

        oId = '{didurl}/{o}'.format(didurl=self.id, o=oName)
        try:
            async with self.ipid.editServiceById(self.id) as editor:
                editor.service['serviceEndpoint']['objects'].append({
                    '@context': 'ips://galacteek.ld/IpfsObject',
                    '@type': 'IpfsObject',
                    'id': oId,
                    'objectPath': objPath,
                    'objectName': path.basename,
                    'objectDescription': description
                })

            return True
        except Exception as err:
            self.ipid.message('Error editing collection service: {}'.format(
                str(err)))
            return False

    def __str__(self):
        return 'IPS: Collection ({name})'.format(
            name=self.endpoint.get('name', 'Unknown')
        )


class LivePeerStreamingService(IPService):
    forTypes = [IPService.SRV_TYPE_LIVEPEER_STREAMING]
    endpointName = 'LivePeerEndpoint'


class PSRendezVousService(IPService):
    forTypes = [IPService.SRV_TYPE_PSRENDEZVOUS]
    endpointName = 'PSRendezVousEndpoint'
