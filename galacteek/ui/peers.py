import os.path
import asyncio
import functools

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

from PyQt5.QtCore import QAbstractItemModel
from PyQt5.QtCore import QModelIndex
from PyQt5.QtCore import QMimeData
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import QUrl
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QVariant
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QPixmap

from galacteek import ensure
from galacteek import partialEnsure
from galacteek import log
from galacteek.ipfs.wrappers import ipfsOp
from galacteek.ipfs.cidhelpers import *
from galacteek.ipfs.ipfsops import *
from galacteek.core.modelhelpers import *
from galacteek.core.models import BaseAbstractItem
from galacteek.core.iphandle import SpaceHandle
from galacteek.dweb.atom import DWEB_ATOM_FEEDFN
from galacteek.did import didExplode

from . import ui_peersmgr
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


def iPeerToolTip(peerId, ipHandle, did, validated):
    return QCoreApplication.translate(
        'PeersManager',
        '''
        <p>
            Peer ID: {0}
        </p>
        <p>Space Handle: {1}</p>
        <p>DID: <b>{2}</b></p>
        <p>{3}</p>
        </p>
        ''').format(peerId, ipHandle, did,
                    'QR Validated' if validated is True else 'Not validated')


class PeerBaseItem(BaseAbstractItem):
    def tooltip(self, col):
        return ''


class PeerTreeItem(PeerBaseItem):
    def __init__(self, peerCtx, parent=None):
        super().__init__(parent=parent)
        self.ctx = peerCtx

    def columnCount(self):
        return 2

    def userData(self, column):
        return self.ctx.peerId

    def tooltip(self, col):
        handle = SpaceHandle(self.ctx.ident.iphandle)
        return iPeerToolTip(
            self.ctx.peerId, str(handle), self.ctx.ipid.did,
            self.ctx.validated)

    def data(self, column):
        handle = self.ctx.spaceHandle

        if column == 0:
            if handle.valid:
                return handle.short
            else:
                return iUnknown()
        if column == 1:
            return self.ctx.ipid.did
        if column == 2:
            return self.ctx.pingavg
        if column == 3:
            return self.ctx.ident.vplanet

        return QVariant(None)

    async def updateServices(self):
        esids = [it.service.id for it in self.childItems]

        async for service in self.ctx.discoverServices():
            if service.id in esids:
                continue

            pSItem = PeerServiceTreeItem(service, parent=self)
            self.appendChild(pSItem)


class PeerServiceTreeItem(PeerBaseItem):
    def __init__(self, service, parent=None):
        super().__init__(parent=parent)
        self.service = service
        self.peerItem = parent

    def columnCount(self):
        return 2

    def userData(self, column):
        return None

    def data(self, column):
        handle = self.peerItem.ctx.spaceHandle
        exploded = didExplode(self.service.id)

        if column == 0:
            if exploded['path']:
                return os.path.join(handle.short,
                                    exploded['path'].lstrip('/'))
        if column == 1:
            return str(self.service.id)

        return QVariant(None)


class PeersModel(QAbstractItemModel):
    def __init__(self, parent=None):
        super(PeersModel, self).__init__(parent)

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
                peer = self.data(idxPeer)
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

        if role == Qt.UserRole:
            return item.userData(index.column())

        elif role == Qt.DisplayRole or role == Qt.EditRole:
            return item.data(index.column())

        elif role == Qt.ToolTipRole:
            return item.tooltip(index.column())

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags

        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.rootItem.data(section)

        return None

    def getItem(self, index):
        if index.isValid():
            item = index.internalPointer()
            if item:
                return item

        return self.rootItem

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
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

        return parentItem.childCount()

    def removeRows(self, position, rows, parent=QModelIndex()):
        parentItem = self.getItem(parent)

        self.beginRemoveRows(parent, position, position + rows - 1)
        success = parentItem.removeChildren(position, rows)
        self.endRemoveRows()

        return success

    async def peerLookup(self, peerId):
        with await self.lock:
            for item in self.rootItem.childItems:
                if not isinstance(item, PeerTreeItem):
                    continue

                if item.ctx.peerId == peerId:
                    return item


class PeersTracker:
    def __init__(self, ctx):
        self.model = PeersModel()

        self.ctx = ctx
        self.ctx.peers.changed.connectTo(self.onPeersChange)
        self.ctx.peers.peerAdded.connectTo(self.onPeerAdded)
        self.ctx.peers.peerModified.connectTo(self.onPeerModified)
        self.ctx.peers.peerDidModified.connectTo(self.onPeerDidModified)
        self.ctx.peers.peerLogout.connectTo(self.onPeerLogout)

    async def onPeerLogout(self, peerId):
        with await self.model.lock:
            for item in self.model.rootItem.childItems:
                if not isinstance(item, PeerTreeItem):
                    continue

                if item.ctx.peerId == peerId:
                    if self.model.removeRows(item.row(), 1):
                        del item

    async def onPeerModified(self, peerId):
        pass

    async def onPeerDidModified(self, peerId, modified):
        if modified:
            peerItem = await self.model.peerLookup(peerId)
            if peerItem:
                await peerItem.updateServices()
                self.model.modelReset.emit()

    async def onPeerAdded(self, peerId):
        peerCtx = self.ctx.peers.getByPeerId(peerId)
        if not peerCtx:
            return

        await self.addPeerToModel(peerId, peerCtx)

    async def addPeerToModel(self, peerId, peerCtx):
        with await self.model.lock:
            peerItem = PeerTreeItem(peerCtx, parent=self.model.rootItem)

            self.model.rootItem.appendChild(peerItem)

            async for service in peerCtx.discoverServices():
                pSItem = PeerServiceTreeItem(service, parent=peerItem)
                peerItem.appendChild(pSItem)

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
            idxId = self.model.index(idx.row(), 1, idx.parent())
            _id = self.model.data(idxId, Qt.DisplayRole)
            self.serviceEntered.emit(_id)
            ensure(self.accessPeerService(_id))

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
        super(PeersServiceSearchDock, self).__init__('Services search', parent)

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
        self.searcher.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.hide()

    def onServiceEntered(self, serviceId):
        self.searchWidget.setVisible(False)
        self.setVisible(False)

    def searchMode(self):
        self.searchWidget.setVisible(True)
        self.setVisible(True)
        self.searcher.setFocus(Qt.OtherFocusReason)


class PeersManager(GalacteekTab):
    def __init__(self, gWindow, peersTracker, **kw):
        super().__init__(gWindow, **kw)

        self.lock = asyncio.Lock()
        self.peersTracker = peersTracker

        self.peersWidget = QWidget()
        self.addToLayout(self.peersWidget)
        self.ui = ui_peersmgr.Ui_PeersManager()
        self.ui.setupUi(self.peersWidget)

        self.ui.peersMgrView.setModel(self.peersTracker.model)

        self.ui.peersMgrView.header().setSectionResizeMode(
            0, QHeaderView.ResizeToContents)
        self.ui.peersMgrView.header().setSectionResizeMode(
            1, QHeaderView.ResizeToContents)

        self.ui.peersMgrView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.peersMgrView.customContextMenuRequested.connect(
            self.onContextMenu)
        self.ui.peersMgrView.doubleClicked.connect(self.onDoubleClick)
        self.ui.peersMgrView.setDragDropMode(QAbstractItemView.DragOnly)

        self.peersSearcher = PeersServiceSearcher(
            self.peersTracker.model, self)
        self.ui.hLayoutTop.addWidget(self.peersSearcher)

        self.app.ipfsCtx.peers.changed.connectTo(self.onPeersChange)
        self.app.ipfsCtx.peers.peerAdded.connectTo(self.onPeerAdded)

    @property
    def model(self):
        return self.peersTracker.model

    async def onPeersChange(self):
        pass

    async def onPeerAdded(self, peerId):
        pass

    def onContextMenu(self, point):
        idx = self.ui.peersMgrView.indexAt(point)
        if not idx.isValid():
            return

        peerId = self.model.data(idx, Qt.UserRole)
        peerCtx = self.peersTracker.ctx.peers.getByPeerId(peerId)

        def menuBuilt(future):
            try:
                menu = future.result()
                menu.exec(self.ui.peersMgrView.mapToGlobal(point))
            except Exception:
                pass

        ensure(self.showPeerContextMenu(peerCtx, point), futcallback=menuBuilt)

    @ipfsOp
    async def showPeerContextMenu(self, ipfsop, peerCtx, point):
        menu = QMenu(self)

        # Services menu
        sMenu = QMenu(iIPServices(), menu)
        sMenu.setToolTipsVisible(True)
        sMenu.setIcon(getPlanetIcon('saturn.png'))

        followAction = QAction(
            iFollow(),
            self,
            triggered=partialEnsure(self.onFollowPeer(peerCtx))
        )

        if peerCtx.peerId == ipfsop.ctx.node.id:
            followAction.setEnabled(False)

        menu.addAction(followAction)
        menu.addSeparator()
        menu.addMenu(sMenu)

        async for service in peerCtx.discoverServices():
            action = QAction(
                getPlanetIcon('uranus.png'),
                str(service),
                sMenu,
                triggered=functools.partial(
                    ensure,
                    self.onAccessPeerService(peerCtx, service)))
            action.setToolTip(service.id)
            sMenu.addAction(action)
            sMenu.addSeparator()

        return menu

    async def onAccessPeerService(self, pCtx, service):
        log.debug('Accessing Peer Service ... '
                  'Peer {peer}, service ID {srvid}'.format(
                      peer=pCtx.peerId,
                      srvid=service.id
                  ))
        endpoint = service.endpoint
        ipfsPath = IPFSPath(endpoint)

        if ipfsPath.valid:
            self.gWindow.addBrowserTab().browseFsPath(ipfsPath)

    def onDoubleClick(self, idx):
        didData = self.model.data(
            self.model.sibling(idx.row(), 1, idx),
            Qt.DisplayRole)
        ensure(self.accessPeerService(didData))

    @ipfsOp
    async def accessPeerService(self, ipfsop, serviceId):
        await self.app.resourceOpener.browseIpService(serviceId)

    @ipfsOp
    async def onFollowPeer(self, ipfsop, peerCtx):
        profile = ipfsop.ctx.currentProfile

        if profile.ipid != peerCtx.ipid:
            await profile.userInfo.follow(
                peerCtx.ipid.did,
                peerCtx.ident.iphandle
            )

    @ipfsOp
    async def followPeerFeed(self, op, peerCtx):
        identMsg = peerCtx.ident
        path = os.path.join(joinIpns(identMsg.dagIpns), DWEB_ATOM_FEEDFN)
        ipfsPath = IPFSPath(path)

        try:
            await self.app.sqliteDb.feeds.follow(ipfsPath.dwebUrl)
        except Exception:
            # TODO
            pass
