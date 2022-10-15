import traceback

from PyQt5.QtCore import QVariant
from PyQt5.QtCore import Qt

from galacteek import ensure
from galacteek.did.ipid import IPService
from galacteek.did import didExplode
from galacteek.ld import uriTermExtract
from galacteek.ui.helpers import getIcon
from galacteek.ui.helpers import getMimeIcon
from galacteek.ui.helpers import getIconFromIpfs
from galacteek.ipfs import ipfsOp
from galacteek.ipfs.cidhelpers import IPFSPath

from . import SparQLListModel
from . import SparQLItemModel
from . import SparQLBaseItem


IpServiceUriRole = Qt.UserRole
IpServiceTypeRole = Qt.UserRole + 1
DidRole = Qt.UserRole + 2


class PeersSparQLModel(SparQLListModel):
    avatars = {}

    def __init__(self, graphUri='urn:ipg:i:am', graph=None,
                 peersTracker=None):
        super().__init__(graphUri=graphUri, graph=graph)

        self.pTracker = peersTracker

    def peerContextByDid(self, did: str):
        return self.pTracker.ctx.peers.byDid.get(did)

    def data(self, index, role=None):
        row = index.row()

        try:
            item = self._results[row]
            did = str(item['did'])
            pCtx = self.peerContextByDid(did)
        except KeyError:
            return QVariant(None)
        except IndexError:
            return QVariant(None)

        try:
            if role == Qt.DisplayRole:
                return str(item['handle'])
            elif role == Qt.UserRole:
                return str(item['did'])
            elif role == Qt.ToolTipRole:
                return str(item['did'])
            elif role == Qt.DecorationRole:
                avurl = str(item['avatarurl'])

                if not pCtx or not pCtx.peerActive:
                    return getIcon('offline.png')

                if avurl not in self.avatars:
                    ensure(self.fetchAvatar(avurl))
                    return getIcon('peers.png')
                else:
                    return self.avatars[avurl]
        except Exception:
            return QVariant(None)

        return QVariant(None)

    @ipfsOp
    async def fetchAvatar(self, ipfsop, url):
        path = IPFSPath(url)

        if path.valid:
            icon = await getIconFromIpfs(ipfsop, str(path))
            if icon:
                self.avatars[url] = icon

    def peersQuery(self):
        return '''
            PREFIX gs: <ips://galacteek.ld/>
            PREFIX did: <ips://galacteek.ld/did>
            PREFIX didv: <https://w3id.org/did#>
            PREFIX passsrv: <ips://galacteek.ld/DwebPassportService>
            PREFIX pass: <ips://galacteek.ld/DwebPassport>

            SELECT ?did ?handle ?pass ?avatarurl
            WHERE {
              ?did a gs:did .
              ?did didv:service ?psrv .

              ?did didv:service ?avsrv .
              ?avsrv a gs:DwebAvatarService .
              ?avsrv didv:serviceEndpoint ?avatarurl .

              ?psrv a gs:DwebPassportService .
              ?psrv didv:serviceEndpoint ?pass .
              ?pass gs:me ?person .
              ?person gs:ipHandleShort ?handle .
            }
            ORDER BY DESC(?handle)
        '''


class ServiceObjectsItem(SparQLBaseItem):
    def icon(self, column):
        return getIcon('folder-open.png')


class PeerServiceItem(SparQLBaseItem):
    def __init__(self, result, service, parent=None):
        super().__init__(data=result, parent=parent)
        self.service = service

    @property
    def srvUri(self):
        return self.itemData.get('srv')

    @property
    def srvType(self):
        # Extract the DID service type from the URI
        return uriTermExtract(self.itemData.get('srvtype', ''))

    def tooltip(self, column):
        return self.srvType

    def data(self, column, role):
        if role == Qt.DisplayRole and column == 0:
            didex = didExplode(self.srvUri)
            if didex:
                return didex['path'].lstrip('/')

            return self.srvUri

        return super().data(column, role)

    def icon(self, column):
        if self.srvType == IPService.SRV_TYPE_DWEBBLOG:
            return getIcon('feather-pen.png')
        elif self.srvType == IPService.SRV_TYPE_AVATAR:
            return getMimeIcon('image/generic')
        elif self.srvType in [IPService.SRV_TYPE_DWEBSITE_GENERIC,
                              IPService.SRV_TYPE_HTTP_SERVICE,
                              IPService.SRV_TYPE_HTTP_FORWARD_SERVICE]:
            return getMimeIcon('text/html')
        elif self.srvType == IPService.SRV_TYPE_GEMINI_CAPSULE:
            return getIcon('gemini.png')
        elif self.srvType == IPService.SRV_TYPE_ATOMFEED:
            return getIcon('atom-feed.png')
        elif self.srvType == IPService.SRV_TYPE_COLLECTION:
            return getIcon('folder-open.png')
        elif self.srvType in [IPService.SRV_TYPE_GENERICPYRAMID,
                              IPService.SRV_TYPE_GALLERY]:
            return getIcon('pyramid-aqua.png')
        else:
            return getIcon('peers.png')


class DIDServicesSparQLModel(SparQLItemModel):
    def __init__(self, graphUri='urn:ipg:i:am', graph=None,
                 peersTracker=None):
        super().__init__(graphUri=graphUri, graph=graph)

        self.pTracker = peersTracker
        self.rootItem = SparQLBaseItem(['Service'])

    def peerContextByDid(self, did: str):
        return self.pTracker.ctx.peers.byDid.get(did)

    def queryForParent(self, parent):
        if parent is self.rootItem and 0:
            return self.servicesQuery(), None
        elif isinstance(parent, PeerServiceItem):
            # If it's an ObjectsCollectionService, list the files in it

            if parent.srvType == 'ObjectsCollectionService':
                return self.collectionObjectsQuery(), {
                    'srv': parent.itemData['srv']
                }

        return None, None

    async def itemFromResult(self, result, parent):
        try:
            service = None
            pCtx = self.peerContextByDid(str(result.get('did')))
            if pCtx:
                service = pCtx.ipid.serviceInstance(str(result['srv']))

            if parent is self.rootItem:
                return PeerServiceItem(result, service, parent=parent)
            elif isinstance(parent, ServiceObjectsItem):
                return None
            elif isinstance(parent, PeerServiceItem):
                return ServiceObjectsItem(result, parent=parent)
        except Exception:
            traceback.print_exc()

    def servicesQuery(self):
        return '''
            PREFIX gs: <ips://galacteek.ld/>
            PREFIX did: <ips://galacteek.ld/did>
            PREFIX didv: <https://w3id.org/did#>

            SELECT ?srv ?srvtype ?did ?srvdescr
            WHERE {
              ?did a gs:did .
              ?did didv:service ?srv .
              ?srv a ?srvtype .
              OPTIONAL { ?srv gs:description ?srvdescr . } .
            }
        '''

    def collectionObjectsQuery(self):
        return '''
            PREFIX gs: <ips://galacteek.ld/>
            PREFIX did: <ips://galacteek.ld/did>
            PREFIX didv: <https://w3id.org/did#>
            PREFIX col: <ips://galacteek.ld/ObjectsCollectionEndpoint#>
            PREFIX ipfsobj: <ips://galacteek.ld/IpfsObject#>

            SELECT ?path ?srv ?obj
            WHERE {
              ?srv a gs:ObjectsCollectionService .
              ?srv didv:serviceEndpoint ?endp .
              ?endp col:objects ?obj .
              ?obj ipfsobj:path ?path .
            }
        '''
