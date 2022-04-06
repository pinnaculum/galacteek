import asyncio

from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QMenu
from PyQt5.QtWidgets import QHeaderView
from PyQt5.QtWidgets import QCompleter
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QDockWidget
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QAbstractItemView
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QApplication

from PyQt5.QtCore import QAbstractItemModel
from PyQt5.QtCore import QModelIndex
from PyQt5.QtCore import QMimeData
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import QUrl
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QVariant
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QBuffer
from PyQt5.QtCore import QByteArray
from PyQt5.QtCore import QIODevice

from PyQt5.QtGui import QPixmap
from PyQt5.QtGui import QColor
from PyQt5.QtGui import QBrush

from galacteek import ensure
from galacteek import log
from galacteek.ipfs.wrappers import ipfsOp
from galacteek.ipfs.cidhelpers import *
from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.paths import posixIpfsPath
from galacteek.core.modelhelpers import *
from galacteek.core.models import BaseAbstractItem
from galacteek.core.iphandle import SpaceHandle
from galacteek.dweb.atom import DWEB_ATOM_FEEDFN
from galacteek.did import didExplode
from galacteek.did.ipid import IPService

from .dids import buildIpServicesMenu
from .forms import ui_peersmgr
from .widgets import *
from .helpers import *
from .dialogs import *
from .i18n import iIPIDLong
from .i18n import iIPServices
from .i18n import iFollow
from .i18n import iUnknown
from .i18n import iIPHandle


def iUsername():
    return QCoreApplication.translate('PeersManager', 'Username')


def iPeerId():
    return QCoreApplication.translate('PeersManager', 'Peer ID')


def iPingAvg():
    return QCoreApplication.translate('PeersManager', 'Ping Average (ms)')


def iLocation():
    return QCoreApplication.translate('PeersManager', 'Location')


def iInvalidDagCID(dagCid):
    return QCoreApplication.translate('PeersManager',
                                      'Invalid DAG CID: {0}').format(dagCid)


def iServicesSearchHelp():
    return QCoreApplication.translate(
        'PeersManager',
        '''
            <p>Type the IP handle of a peer to search for services</p>
            <p>Using <b>/</b> after the handle will popup the services
            list. Hit enter to enter the service</p>
        ''')


def iPeerToolTip(avatarUrl, peerId, ipHandle, did, validated, authenticated,
                 avgPingMs):
    return QCoreApplication.translate(
        'PeersManager',
        '''
        <p><img src="{0}"/></p>
        <p>Handle: {2}</p>
        <p>DID: <b>{3}</b></p>
        <p>{4}</p>
        <p>{5}</p>
        <p>Average ping: {6}</p>
        </p>
        ''').format(avatarUrl, peerId, ipHandle, did,
                    'QR Validated' if validated is True else 'Not validated',
                    'DID Auth OK' if authenticated is True else 'No Auth',
                    f'<b>{avgPingMs}</b> ms' if avgPingMs >= 0 else
                    'Unreachable')


ItemTypeRole = Qt.UserRole + 1
PeerIdRole = Qt.UserRole + 2
PeerDidRole = Qt.UserRole + 3
PeerHandleRole = Qt.UserRole + 4


def peerToolTip(ctx):
    handle = SpaceHandle(ctx.iphandle)

    try:
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.WriteOnly)
        ctx.avatarPixmapScaled(128, 128).save(buffer, 'PNG')
        buffer.close()

        avatarUrl = 'data:image/png;base64, {}'.format(
            bytes(buffer.data().toBase64()).decode()
        )
    except Exception:
        avatarUrl = ':/share/icons/unknown-file.png'

    return iPeerToolTip(
        avatarUrl,
        ctx.peerId,
        str(handle),
        ctx.ipid.did,
        ctx.validated,
        ctx.authenticated,
        ctx.pingAvg()
    )


class PeerBaseItem(BaseAbstractItem):
    itemType = None

    def tooltip(self, col):
        return ''

    def icon(self):
        return getIcon('unknown-file.png')


class PeerTreeItem(PeerBaseItem):
    itemType = 'peer'

    def __init__(self, piCtx, parent=None):
        super(PeerTreeItem, self).__init__(data=None, parent=parent)
        self.ctx = piCtx

    def columnCount(self):
        return 2

    def userData(self, column):
        return self.ctx.peerId

    def tooltip(self, col):
        return peerToolTip(self.ctx)

    def data(self, column, role):
        handle = self.ctx.spaceHandle

        if role == Qt.DisplayRole or role == Qt.EditRole:
            if column == 0:
                if handle.valid:
                    return handle.human
                else:
                    return iUnknown()
            if column == 1:
                return self.ctx.ipid.did

        elif role == Qt.BackgroundRole and 0:
            if self.ctx.ipid.local:
                color = QColor('#cce4ff')
            else:
                if self.ctx.peerActive:
                    color = QColor('#90C983')
                else:
                    color = QColor('#F0F7F7')
            return QBrush(color)
        elif role == PeerIdRole:
            return self.ctx.peerId
        elif role == PeerDidRole:
            return self.ctx.ipid.did
        elif role == PeerHandleRole:
            return str(handle)

        return QVariant(None)

    async def updateServices(self):
        esids = [it.service.id for it in self.childItems]

        async for service in self.ctx.ipid.discoverServices():
            if service.id in esids:
                if service.container:
                    for it in self.childItems:
                        if it.service.id == service.id:
                            await it.updateContained()

                continue

            pSItem = PeerServiceTreeItem(service, parent=self)
            self.appendChild(pSItem)

            if service.container:
                await pSItem.updateContained()

    def icon(self):
        if self.ctx.peerActive:
            return self.ctx.avatarPixmapScaled(32, 32)
        else:
            return getIcon('offline.png')


class PeerServiceObjectTreeItem(PeerBaseItem):
    itemType = 'serviceObject'

    def __init__(self, sObject, peerItem, parent=None):
        super().__init__(parent=parent)
        self.sObject = sObject
        self.peerItem = peerItem
        self.serviceItem = parent

    def columnCount(self):
        return 2

    def userData(self, column):
        pass

    def icon(self):
        return getIconIpfs64()

    def tooltip(self, col):
        return self.sObject.get('id')

    def data(self, column, role):
        if column == 0:
            handle = self.peerItem.ctx.spaceHandle
            exploded = didExplode(self.sObject['id'])

            if exploded and exploded['path']:
                return posixIpfsPath.join(handle.short,
                                          exploded['path'].lstrip('/'))
        if column == 1:
            return self.sObject['id']

        return QVariant(None)


class PeerServiceTreeItem(PeerBaseItem):
    itemType = 'service'

    def __init__(self, service, parent=None):
        super(PeerServiceTreeItem, self).__init__(parent=parent)
        self.service = service
        self.peerItem = parent

    def columnCount(self):
        return 3

    def userData(self, column):
        pass

    def tooltip(self, col):
        return self.service.id

    def icon(self):
        if not self.service:
            return None

        if self.service.type == IPService.SRV_TYPE_DWEBBLOG:
            return getIcon('blog.png')
        elif self.service.type == IPService.SRV_TYPE_DWEBSITE_GENERIC:
            return getMimeIcon('text/html')
        elif self.service.type == IPService.SRV_TYPE_ATOMFEED:
            return getIcon('atom-feed.png')
        elif self.service.type == IPService.SRV_TYPE_COLLECTION:
            return getIcon('folder-open.png')
        elif self.service.type in [IPService.SRV_TYPE_GENERICPYRAMID,
                                   IPService.SRV_TYPE_GALLERY]:
            return getIcon('pyramid-aqua.png')
        else:
            return getIconIpfs64()

    def data(self, column, role):
        if column == 0:
            handle = self.peerItem.ctx.spaceHandle
            exploded = didExplode(self.service.id)

            if exploded['path']:
                return posixIpfsPath.join(handle.human,
                                          exploded['path'].lstrip('/'))
        if column == 1:
            return str(self.service.id)

        return QVariant(None)

    async def updateContained(self):
        oids = [it.sObject['id'] for it in self.childItems]

        async for obj in self.service.contained():
            if obj['id'] in oids:
                continue

            pSItem = PeerServiceObjectTreeItem(
                obj, self.peerItem, parent=self)
            self.appendChild(pSItem)


class PeersModel(QAbstractItemModel):
    def __init__(self, parent=None):
        super(PeersModel, self).__init__(parent)

        self.app = QApplication.instance()
        self.rootItem = PeerBaseItem([
            iIPHandle(),
            iIPIDLong()
        ])
        self.lock = asyncio.Lock()

    def mimeData(self, indexes):
        mimedata = QMimeData()

        for idx in indexes:
            idxPeer = self.index(idx.row(), 1, idx.parent())
            if idxPeer.isValid():
                peer = self.data(idxPeer, Qt.DisplayRole)
                mimedata.setUrls([QUrl('galacteekpeer:{}'.format(peer))])
                break

        return mimedata

    def canDropMimeData(self, data, action, row, column, parent):
        return True

    def dropMimeData(self, data, action, row, column, parent):
        if data.hasUrls():
            return True

    def columnCount(self, parent):
        if parent.isValid():
            return parent.internalPointer().columnCount()
        else:
            return self.rootItem.columnCount()

    def data(self, index, role):
        if not index.isValid():
            return None

        item = index.internalPointer()

        specRoles = [
            PeerIdRole,
            PeerDidRole,
            PeerHandleRole,
            Qt.DisplayRole,
            Qt.BackgroundRole,
            Qt.EditRole
        ]

        if role in specRoles:
            return item.data(index.column(), role)

        elif role == Qt.UserRole:
            return item.userData(index.column())

        elif role == ItemTypeRole:
            return item.itemType

        elif role == Qt.DecorationRole:
            return item.icon()

        elif role == Qt.ToolTipRole:
            return item.tooltip(index.column())

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags

        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.rootItem.data(section, role)

        return None

    def getItem(self, index):
        if index.isValid():
            item = index.internalPointer()
            if item:
                return item

        return self.rootItem

    def index(self, row, column, parent=None):
        if not parent or not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QModelIndex()

    def indexRoot(self):
        return self.createIndex(self.rootItem.row(), 0)

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()

        childItem = index.internalPointer()
        if childItem is None:
            return QModelIndex()

        if not isinstance(childItem, PeerBaseItem):
            return QModelIndex()

        parentItem = childItem.parent()

        if parentItem == self.rootItem:
            return QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def rowCount(self, parent):
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        if parentItem:
            return parentItem.childCount()
        else:
            return 0

    def removeRows(self, position, rows, parent=QModelIndex()):
        parentItem = self.getItem(parent)

        self.beginRemoveRows(parent, position, position + rows - 1)
        success = parentItem.removeChildren(position, rows)
        self.endRemoveRows()

        return success

    async def peerLookupByDid(self, did):
        async with self.lock:
            for item in self.rootItem.childItems:
                if not isinstance(item, PeerTreeItem):
                    continue

                if item.ctx.ipid.did == did:
                    return item

    def peerIdRegistered(self, peerId):
        return len(self.match(self.indexRoot(), PeerIdRole, QVariant(peerId),
                              1, Qt.MatchExactly | Qt.MatchWrap)) > 0

    def didRegistered(self, did):
        return len(self.match(self.indexRoot(), PeerDidRole, did,
                              1, Qt.MatchExactly | Qt.MatchWrap)) > 0


class PeersTracker:
    def __init__(self, ctx):
        self.model = PeersModel()

        self.ctx = ctx
        self.ctx.peers.changed.connectTo(self.onPeersChange)
        self.ctx.peers.peerAdded.connectTo(self.onPeerAdded)
        self.ctx.peers.peerModified.connectTo(self.onPeerModified)
        self.ctx.peers.peerDidModified.connectTo(self.onPeerDidModified)
        self.ctx.peers.peerLogout.connectTo(self.onPeerLogout)

    def peerDataChangedEmit(self, peerItem):
        self.model.dataChanged.emit(
            self.model.index(peerItem.row(), 0),
            self.model.index(peerItem.row() + 1, 0)
        )

    async def onPeerLogout(self, peerId):
        async with self.model.lock:
            for item in self.model.rootItem.childItems:
                if not isinstance(item, PeerTreeItem):
                    continue

                if item.ctx.peerId == peerId:
                    if self.model.removeRows(item.row(), 1):
                        del item

    async def onPeerModified(self, piCtx):
        peerItem = await self.model.peerLookupByDid(piCtx.ipid.did)

        if peerItem:
            self.peerDataChangedEmit(peerItem)

    async def onPeerDidModified(self, piCtx, modified):
        if modified:
            peerItem = await self.model.peerLookupByDid(piCtx.ipid.did)

            if peerItem:
                await peerItem.updateServices()
                self.peerDataChangedEmit(peerItem)
                await peerItem.ctx.fetchAvatar()

    async def onPeerAdded(self, piCtx):
        if not self.model.didRegistered(piCtx.ipid.did):
            await self.addPeerToModel(piCtx)

    async def addPeerToModel(self, piCtx):
        peerItem = PeerTreeItem(
            piCtx, parent=self.model.rootItem)

        ensure(piCtx.fetchAvatar())

        self.model.rootItem.appendChild(peerItem)

        try:
            await peerItem.updateServices()
        except Exception:
            pass

        self.model.modelReset.emit()

    async def onPeersChange(self):
        pass


class PeersServicesCompleter(QCompleter):
    def splitPath(self, path):
        hop = path.split('/')
        return hop

    def pathFromIndex(self, index):
        data = self.model().data(index, Qt.EditRole)
        return data


class PeersServiceSearcher(QLineEdit):
    serviceEntered = pyqtSignal(str)

    def __init__(self, model, parent):
        super().__init__(parent)

        self.setClearButtonEnabled(True)
        self.setObjectName('ipServicesSearcher')
        self.setToolTip(iServicesSearchHelp())

        self.app = QApplication.instance()
        self.model = model

        self.completer = PeersServicesCompleter(self)
        self.completer.setModel(model)
        self.completer.setModelSorting(QCompleter.UnsortedModel)
        self.completer.setWidget(self)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setCompletionColumn(0)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.activated.connect(self.onCompletion)
        self.setCompleter(self.completer)
        self.returnPressed.connect(self.onCompletionAccess)

    def onCompletionAccess(self):
        service = self.text()

        idxes = modelSearch(self.model, search=service)
        if len(idxes) == 1:
            self.clear()
            idx = idxes.pop()
            idxDid = self.model.index(
                idx.parent().row(), 1, idx.parent().parent())
            idxId = self.model.index(idx.row(), 1, idx.parent())

            serviceId = self.model.data(idxId, Qt.DisplayRole)
            did = self.model.data(idxDid, Qt.DisplayRole)

            self.serviceEntered.emit(serviceId)

            ensure(
                self.app.towers['did'].didServiceOpenRequest.emit(
                    did, serviceId, {}
                )
            )

    @ipfsOp
    async def accessPeerService(self, ipfsop, serviceId):
        self.clear()
        await self.app.resourceOpener.browseIpService(serviceId)

    def onCompletion(self, text):
        pass


class PeersServiceSearchDockWidget(QWidget):
    def __init__(self, parent):
        super().__init__(parent)

        self.hLayout = QHBoxLayout()
        self.setLayout(self.hLayout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.hide()


class PeersServiceSearchDock(QDockWidget):
    def __init__(self, peersTracker, parent):
        super(PeersServiceSearchDock, self).__init__(
            'IP services searcher', parent)

        self.setObjectName('ipServicesSearchDock')

        self.peersTracker = peersTracker
        self.setFeatures(QDockWidget.DockWidgetClosable)

        self.label = QLabel(self)
        self.label.setPixmap(
            QPixmap(':/share/icons/ipservice.png').scaled(32, 32))

        self.searcher = PeersServiceSearcher(self.peersTracker.model, self)
        self.searcher.serviceEntered.connect(self.onServiceEntered)

        self.searchWidget = PeersServiceSearchDockWidget(self)
        self.searchWidget.hLayout.addWidget(self.label)
        self.searchWidget.hLayout.addWidget(self.searcher)
        self.searchWidget.hide()

        self.setWidget(self.searchWidget)
        self.hide()

    def onServiceEntered(self, serviceId):
        self.searchWidget.setVisible(False)
        self.setVisible(False)

    def searchMode(self):
        self.searchWidget.setVisible(True)
        self.setVisible(True)
        self.searcher.setFocus(Qt.OtherFocusReason)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)


class PeersManager(GalacteekTab):
    def __init__(self, gWindow, peersTracker, **kw):
        super().__init__(gWindow, sticky=True)

        self.lock = asyncio.Lock()
        self.peersTracker = peersTracker

        self.peersWidget = QWidget()
        self.addToLayout(self.peersWidget)
        self.ui = ui_peersmgr.Ui_PeersManager()
        self.ui.setupUi(self.peersWidget)

        self.ui.peersMgrView.setModel(self.peersTracker.model)

        self.ui.peersMgrView.header().setSectionResizeMode(
            0, QHeaderView.ResizeToContents)
        self.ui.peersMgrView.hideColumn(1)

        self.ui.peersMgrView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.peersMgrView.customContextMenuRequested.connect(
            self.onContextMenu)
        self.ui.peersMgrView.doubleClicked.connect(self.onDoubleClick)
        self.ui.peersMgrView.setDragDropMode(QAbstractItemView.DragOnly)
        self.ui.peersMgrView.setHeaderHidden(True)

        self.app.ipfsCtx.peers.changed.connectTo(self.onPeersChange)
        self.app.ipfsCtx.peers.peerAdded.connectTo(self.onPeerAdded)

    @property
    def model(self):
        return self.peersTracker.model

    async def onPeersChange(self):
        pass

    async def onPeerAdded(self, piCtx):
        pass

    def onContextMenu(self, point):
        idx = self.ui.peersMgrView.indexAt(point)
        if not idx.isValid():
            return

        handle = self.model.data(idx, PeerHandleRole)
        piCtx = self.peersTracker.ctx.peers.getByHandle(handle)

        if not piCtx:
            return

        def menuBuilt(future):
            try:
                menu = future.result()
                menu.exec(self.ui.peersMgrView.mapToGlobal(point))
            except Exception as e:
                log.debug(str(e))

        ensure(self.showPeerContextMenu(piCtx, point), futcallback=menuBuilt)

    @ipfsOp
    async def showPeerContextMenu(self, ipfsop, piCtx, point):
        menu = QMenu(self)

        # Services menu
        sMenu = QMenu(iIPServices(), menu)
        sMenu.setToolTipsVisible(True)
        sMenu.setIcon(getPlanetIcon('saturn.png'))

        followAction = QAction(
            iFollow(),
            self,
            triggered=lambda checked: ensure(self.onFollowPeer(piCtx))
        )

        if piCtx.peerId == ipfsop.ctx.node.id:
            followAction.setEnabled(False)

        menu.addAction(followAction)
        menu.addSeparator()
        menu.addMenu(sMenu)

        await buildIpServicesMenu(piCtx.ipid, sMenu)

        return menu

    def onDoubleClick(self, idx):
        itemType = self.model.data(
            self.model.sibling(idx.row(), 0, idx),
            ItemTypeRole
        )

        didData = self.model.data(
            self.model.sibling(idx.row(), 1, idx),
            Qt.DisplayRole)

        if itemType == 'service':
            ensure(
                self.app.towers['did'].didServiceOpenRequest.emit(
                    None, didData, {}
                )
            )
        elif itemType == 'serviceObject':
            serviceId = self.model.data(
                self.model.sibling(idx.parent().row(), 1, idx.parent()),
                Qt.DisplayRole)
            if serviceId:
                ensure(
                    self.app.towers['did'].didServiceObjectOpenRequest.emit(
                        None, serviceId, didData
                    )
                )

    @ipfsOp
    async def accessPeerService(self, ipfsop, serviceId):
        await self.app.resourceOpener.browseIpService(serviceId)

    @ipfsOp
    async def onFollowPeer(self, ipfsop, piCtx):
        profile = ipfsop.ctx.currentProfile

        await profile.userInfo.follow(
            piCtx.ipid.did,
            piCtx.iphandle
        )

    @ipfsOp
    async def followPeerFeed(self, op, piCtx):
        identMsg = piCtx.ident

        path = posixIpfsPath.join(joinIpns(identMsg.dagIpns), DWEB_ATOM_FEEDFN)
        ipfsPath = IPFSPath(path)

        try:
            await self.app.sqliteDb.feeds.follow(ipfsPath.ipfsUrl)
        except Exception:
            # TODO
            pass
