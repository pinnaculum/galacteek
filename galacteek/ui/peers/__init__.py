import asyncio
from rdflib import URIRef

from PyQt5.QtWidgets import QHeaderView
from PyQt5.QtWidgets import QListView
from PyQt5.QtWidgets import QWidget

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QBuffer
from PyQt5.QtCore import QByteArray
from PyQt5.QtCore import QIODevice
from PyQt5.QtCore import QSize

from galacteek import ensure
from galacteek.ipfs.cidhelpers import *
from galacteek.ipfs.ipfsops import *
from galacteek.core import runningApp
from galacteek.core.modelhelpers import *
from galacteek.core.iphandle import SpaceHandle

from galacteek.core.models.sparql.peers import PeersSparQLModel
from galacteek.core.models.sparql.peers import DIDServicesSparQLModel
from galacteek.core.models.sparql.peers import PeerServiceItem
from galacteek.core.models.sparql.peers import ServiceObjectsItem

from ..forms import ui_peersgraph
from ..forms import ui_peerservicesview
from ..widgets import *
from ..helpers import *
from ..dialogs import *


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


class PeersTracker:
    # TODO: Get rid of this object, useless now since we use a sparql model

    def __init__(self, ctx):
        self.ctx = ctx

        if 0:
            self.ctx.peers.changed.connectTo(self.onPeersChange)
            self.ctx.peers.peerAdded.connectTo(self.onPeerAdded)
            self.ctx.peers.peerModified.connectTo(self.onPeerModified)
            self.ctx.peers.peerDidModified.connectTo(self.onPeerDidModified)
            self.ctx.peers.peerLogout.connectTo(self.onPeerLogout)


class PeerView(QWidget):
    def __init__(self, did: str, parent=None):
        super().__init__(parent)

        self.app = runningApp()
        self.did = did
        self.model = DIDServicesSparQLModel(graphUri='urn:ipg:i:am',
                                            peersTracker=self.app.peersTracker)

        self.ui = ui_peerservicesview.Ui_Form()
        self.ui.setupUi(self)
        self.ui.did.setText(self.did)

        self.ui.servicesView.setModel(self.model)
        self.ui.servicesView.setHeaderHidden(True)
        self.ui.servicesView.header().setSectionResizeMode(
            QHeaderView.ResizeToContents)
        self.ui.servicesView.setItemsExpandable(True)
        self.ui.servicesView.doubleClicked.connect(self.onDoubleClick)
        self.ui.servicesView.setIconSize(QSize(48, 48))

        ensure(self.updateModel())

    async def updateModel(self):
        await self.model.graphBuild(self.model.servicesQuery(),
                                    bindings={'did': URIRef(self.did)})
        await asyncio.sleep(0)

        self.ui.servicesView.expandAll()

    def onDoubleClick(self, idx):
        item = self.model.getItem(idx)

        if isinstance(item, PeerServiceItem):
            srvid = str(item.itemData['srv'])
            did = str(item.itemData['did'])

            # TODO: use PS emission instead of the tower
            ensure(
                self.app.towers['did'].didServiceOpenRequest.emit(
                    did, srvid, {}
                )
            )
        elif isinstance(item, ServiceObjectsItem):
            path = str(item.itemData.get('path'))

            if path:
                ensure(self.app.resourceOpener.open(path))


class PeersManager(GalacteekTab):
    def __init__(self, gWindow, peersTracker, **kw):
        super().__init__(gWindow, sticky=True)

        self.lock = asyncio.Lock()
        self.peersTracker = peersTracker

        self.peersWidget = QWidget()
        self.addToLayout(self.peersWidget)
        self.ui = ui_peersgraph.Ui_PeersManager()
        self.ui.setupUi(self.peersWidget)

        self.model = PeersSparQLModel(graphUri='urn:ipg:i:am',
                                      peersTracker=self.peersTracker)

        self.ui.peersGraphView.setModel(self.model)
        self.ui.peersGraphView.setViewMode(QListView.IconMode)
        self.ui.peersGraphView.setIconSize(QSize(64, 64))

        self.ui.peersGraphView.doubleClicked.connect(self.onDoubleClick)

        self.app.ipfsCtx.peers.changed.connectTo(self.onPeersChange)
        self.app.ipfsCtx.peers.peerAdded.connectTo(self.onPeerAdded)

        self.showHideBackButton()
        self.ui.backButton.clicked.connect(self.onBackClicked)
        self.refreshModel()

    def refreshModel(self):
        self.model.graphQuery(self.model.peersQuery())

    def showHideBackButton(self):
        self.ui.backButton.setVisible(self.ui.stack.count() > 1)

    def onBackClicked(self):
        self.ui.stack.removeWidget(self.ui.stack.currentWidget())
        self.ui.stack.setCurrentIndex(0)
        self.showHideBackButton()

    async def onPeersChange(self):
        pass

    async def onPeerAdded(self, piCtx):
        pass

    def showEvent(self, event):
        self.refreshModel()

    def onDoubleClick(self, idx):
        did = self.model.data(idx, Qt.UserRole)
        pv = PeerView(did, parent=self.ui.stack)
        self.ui.stack.addWidget(pv)
        self.ui.stack.setCurrentWidget(pv)

        self.showHideBackButton()
