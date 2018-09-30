import asyncio
import os.path

from PyQt5.QtWidgets import QTreeView, QMenu, QHeaderView, QPushButton
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import QObject, QCoreApplication

from galacteek import asyncify, ensure
from galacteek.ipfs.wrappers import ipfsOp
from galacteek.ipfs.dag import DAGQuery
from galacteek.ipfs.cidhelpers import *
from galacteek.ipfs.ipfsops import *

from . import ui_peersmgr
from .widgets import *
from .modelhelpers import *
from .helpers import *
from .dialogs import *

def iUsername():
    return QCoreApplication.translate('PeersManager', 'Username')

def iPeerId():
    return QCoreApplication.translate('PeersManager', 'Peer ID')

def iPingAvg():
    return QCoreApplication.translate('PeersManager', 'Ping Average (ms)')

def iInvalidDagCID(dagCid):
    return QCoreApplication.translate('PeersManager',
            'Invalid DAG CID: {0}').format(dagCid)

class PeersModel(QStandardItemModel):
    pass

class PeersTracker(QObject):
    def __init__(self, ctx):
        super().__init__()
        self.model = PeersModel()
        self.model.setHorizontalHeaderLabels([
            iUsername(),
            iPeerId(),
            iPingAvg(),
            ''
        ])
        self.ctx = ctx
        self.ctx.peers.changed.connect(self.onPeersChange)
        self.ctx.peers.peerAdded.connect(self.onPeerAdded)
        self.ctx.peers.peerModified.connect(self.onPeerModified)
        self.ctx.peers.peerLogout.connect(self.onPeerLogout)
        self._peersRows = {}

    @property
    def modelRoot(self):
        return self.model.invisibleRootItem()

    @property
    def peersRows(self):
        return self._peersRows

    def onPeerLogout(self, peerId):
        ret = modelSearch(self.model,
                parent=self.modelRoot.index(),
                search=peerId, delete=True)

    def onPeerModified(self, peerId):
        entry = self.ctx.peers.getByPeerId(peerId)
        if not entry:
            return

        row = self._peersRows.get(peerId, None)
        if row:
            row[0].setText(entry['identmsg'].username)

        #ret = modelSearch(self.model,
        #        parent=self.modelRoot.index(),
        #        search=peerId, delete=True)
        #self.addPeerFromEntry(peerId, entry)

    def onPeerAdded(self, peerId):
        entry = self.ctx.peers.getByPeerId(peerId)
        if not entry:
            return

        self.addPeerFromEntry(peerId, entry)

    def addPeerFromEntry(self, peerId, entry):
        row = [
            UneditableItem(entry['identmsg'].username),
            UneditableItem(peerId),
            UneditableItem(str(entry['pingavg'])),
            UneditableItem(''),
        ]
        row2 = [
            UneditableItem('Joined: {0}'.format(entry['identmsg'].dateCreated)),
            UneditableItem(peerId),
        ]

        self.modelRoot.appendRow(row)
        idx = self.model.indexFromItem(row[3])

        self._peersRows[peerId] = row
        root = row[0]
        root.appendRow(row2)

    def onPeersChange(self):
        pass

class PeersManager(GalacteekTab):
    def __init__(self, gWindow, peersTracker, **kw):
        super().__init__(gWindow, **kw)

        self.peersTracker = peersTracker
        self.ui = ui_peersmgr.Ui_PeersManager()
        self.ui.setupUi(self)

        self.ui.tree.setModel(self.peersTracker.model)
        self.ui.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.ui.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.ui.tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)

        self.ui.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.tree.customContextMenuRequested.connect(self.onContextMenu)
        self.ui.tree.doubleClicked.connect(self.onDoubleClick)

        self.ui.search.returnPressed.connect(self.onSearch)

        self.app.ipfsCtx.peers.changed.connect(self.onPeersChange)
        self.app.ipfsCtx.peers.peerAdded.connect(self.onPeerAdded)

    @property
    def model(self):
        return self.peersTracker.model

    def onSearch(self):
        search = self.ui.search.text()
        if len(search) > 0:
            self.ui.tree.keyboardSearch(search)

    def onPeersChange(self):
        self.ui.peersCountLabel.setText(str(self.app.ipfsCtx.peers.peersCount))

    def onPeerAdded(self, peerId):
        def openPeer(id):
            entry = self.peersTracker.ctx.peers.getByPeerId(id)
            ensure(self.explorePeerHome(entry))

        def followPeer(id):
            entry = self.peersTracker.ctx.peers.getByPeerId(id)

            runDialog(AddFeedDialog, self.app.marksLocal,
                    joinIpns(entry['identmsg'].dagIpns),
                    feedName=entry['identmsg'].username)

        for peerId, row in self.peersTracker.peersRows.items():
            idx = self.model.indexFromItem(row[3])
            if self.ui.tree.indexWidget(idx) != None:
                continue
            btnEx = QPushButton('Explore')
            btnEx.setFixedSize(100, 20)
            btnEx.clicked.connect(lambda: openPeer(peerId))

            self.ui.tree.setIndexWidget(idx, btnEx)

    def onContextMenu(self, point):
        idx = self.tree.indexAt(point)
        if not idx.isValid():
            return

        idxPeerId = self.model.sibling(idx.row(), 1, idx)
        peerId = self.model.data(idxPeerId)

        menu = QMenu()
        menu.exec(self.tree.mapToGlobal(point))

    def onDoubleClick(self, idx):
        idxPeerId = self.model.sibling(idx.row(), 1, idx)
        peerId = self.model.data(idxPeerId)
        entry = self.peersTracker.ctx.peers.getByPeerId(peerId)

        ensure(self.explorePeerHome(entry))

    @ipfsOp
    async def explorePeerHome(self, op, entry):
        identMsg = entry['identmsg']

        if not await op.hasDagCommand():
            log.debug('No DAG support')
            return

        dagCid = identMsg.dagCid
        if not cidValid(dagCid):
            log.debug('invalid DAG CID: {}'.format(dagCid))
            return messageBox(iInvalidDagCID(dagCid))

        self.gWindow.addBrowserTab().browseFsPath(
                os.path.join(joinIpns(identMsg.dagIpns), 'index.html'))
        return

        try:
            async with DAGQuery(dagCid=dagCid) as q:
                home = await q.resolve('home/index.html')

                if home:
                    self.gWindow.addBrowserTab().browseFsPath(
                        q.path('home/index.html'))
        except Exception as err:
            pass
