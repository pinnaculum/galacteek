import os.path
import asyncio
import functools

from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QMenu
from PyQt5.QtWidgets import QHeaderView
from PyQt5.QtWidgets import QWidget

from PyQt5.QtCore import QAbstractItemModel
from PyQt5.QtCore import QModelIndex
from PyQt5.QtCore import QMimeData
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import QUrl
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QVariant
from PyQt5.QtWidgets import QAbstractItemView

from galacteek import ensure
from galacteek import partialEnsure
from galacteek import log
from galacteek.ipfs.wrappers import ipfsOp
from galacteek.ipfs.cidhelpers import *
from galacteek.ipfs.ipfsops import *
from galacteek.core.modelhelpers import *
from galacteek.core.models import BaseAbstractItem
from galacteek.dweb.atom import DWEB_ATOM_FEEDFN

from . import ui_peersmgr
from .widgets import *
from .helpers import *
from .dialogs import *
from .i18n import iVirtualPlanet
from .i18n import iIPIDLong
from .i18n import iIPServices
from .i18n import iFollow


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


def iPeerToolTip(peerId, did):
    return QCoreApplication.translate(
        'PeersManager',
        '''
        <p>
            <b>{0}</b>
            <b>{1}</b>
        </p>
        ''').format(peerId, did)


class PeerBaseItem(BaseAbstractItem):
    def tooltip(self, col):
        return ''


class PeerTreeItem(PeerBaseItem):
    def __init__(self, peerCtx, parent=None):
        super().__init__(parent=parent)
        self.ctx = peerCtx

    def columnCount(self):
        return 4

    def userData(self, column):
        return self.ctx.peerId

    def tooltip(self, col):
        return iPeerToolTip(self.ctx.peerId, self.ctx.ipid.did)

    def data(self, column):
        if column == 0:
            return self.ctx.ident.iphandle
        if column == 1:
            return self.ctx.ipid.did
        if column == 2:
            return self.ctx.pingavg
        if column == 3:
            return self.ctx.ident.vplanet

        return QVariant(None)


class PeersModel(QAbstractItemModel):
    def __init__(self, parent=None):
        super(PeersModel, self).__init__(parent)

        self.rootItem = PeerBaseItem([
            iUsername(),
            iIPIDLong(),
            iPingAvg(),
            iVirtualPlanet(),
            ''
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

        elif role == Qt.DisplayRole:
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


class PeersTracker:
    def __init__(self, ctx):
        self.model = PeersModel()

        self.ctx = ctx
        self.ctx.peers.changed.connectTo(self.onPeersChange)
        self.ctx.peers.peerAdded.connectTo(self.onPeerAdded)
        self.ctx.peers.peerModified.connectTo(self.onPeerModified)
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
            self.model.modelReset.emit()

    async def onPeersChange(self):
        pass


class PeersManager(GalacteekTab):
    def __init__(self, gWindow, peersTracker, **kw):
        super().__init__(gWindow, **kw)

        self.lock = asyncio.Lock()
        self.peersTracker = peersTracker

        self.peersWidget = QWidget()
        self.addToLayout(self.peersWidget)
        self.ui = ui_peersmgr.Ui_PeersManager()
        self.ui.setupUi(self.peersWidget)

        self.ui.tree.setModel(self.peersTracker.model)

        self.ui.tree.header().setSectionResizeMode(
            0, QHeaderView.ResizeToContents)
        self.ui.tree.header().setSectionResizeMode(
            1, QHeaderView.ResizeToContents)
        self.ui.tree.header().setSectionResizeMode(
            2, QHeaderView.ResizeToContents)

        self.ui.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.tree.customContextMenuRequested.connect(self.onContextMenu)
        self.ui.tree.doubleClicked.connect(self.onDoubleClick)
        self.ui.tree.setDragDropMode(QAbstractItemView.DragOnly)

        self.ui.search.returnPressed.connect(self.onSearch)

        self.app.ipfsCtx.peers.changed.connectTo(self.onPeersChange)
        self.app.ipfsCtx.peers.peerAdded.connectTo(self.onPeerAdded)

    @property
    def model(self):
        return self.peersTracker.model

    def onSearch(self):
        search = self.ui.search.text()
        if len(search) > 0:
            self.ui.tree.keyboardSearch(search)

    async def onPeersChange(self):
        pass

    async def onPeerAdded(self, peerId):
        pass

    def onContextMenu(self, point):
        idx = self.ui.tree.indexAt(point)
        if not idx.isValid():
            return

        peerId = self.model.data(idx, Qt.UserRole)
        peerCtx = self.peersTracker.ctx.peers.getByPeerId(peerId)

        def menuBuilt(future):
            try:
                menu = future.result()
                menu.exec(self.ui.tree.mapToGlobal(point))
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
        # XXX
        # return

        peerId = self.model.data(idx, Qt.UserRole)
        peerCtx = self.peersTracker.ctx.peers.getByPeerId(peerId)

        if peerCtx:
            ensure(self.explorePeerHome(peerCtx))

    @ipfsOp
    async def onFollowPeer(self, ipfsop, peerCtx):
        profile = ipfsop.ctx.currentProfile

        if profile.ipid != peerCtx.ipid:
            async with profile.userInfo as dag:
                section = dag.root['following'].setdefault('main', [])
                section.append({
                    'iphandle': peerCtx.ident.iphandle,
                    'did': peerCtx.ipid.did
                })

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
