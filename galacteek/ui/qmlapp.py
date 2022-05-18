from pathlib import Path

from PyQt5.QtQml import QQmlEngine
from PyQt5.QtQml import qmlRegisterType

from PyQt5.QtQuickWidgets import QQuickWidget

from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QStackedWidget
from PyQt5.QtWidgets import QVBoxLayout

from PyQt5.QtCore import QUrl
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtCore import pyqtSlot

from galacteek import log

from galacteek.dweb.channels.g import GHandler
from galacteek.dweb.channels.ld import LDHandler
from galacteek.dweb.channels.sparql import SparQLHandler
from galacteek.dweb.channels.ipid import IPIDHandler
from galacteek.dweb.channels.ipfs import IPFSHandler
from galacteek.dweb.channels.ipfs import IpfsObjectInterface
from galacteek.dweb.channels.ontolochain import OntoloChainHandler
from galacteek.dweb.channels.graphs import *
from galacteek.dweb.channels.unixfs import UnixFsDirModel

from galacteek.services import getByDotName

from galacteek.qml import quickEnginedWidget

from .helpers import *
from .dialogs import *
from .i18n import *
from .widgets import *

from galacteek.core import runningApp
from galacteek.core.fswatcher import FileWatcher
from galacteek.core.ps import keyPsJson


class IHandler(QObject):
    sizeChanged = pyqtSignal(int, int)
    size = None

    @pyqtSlot(result=int)
    def getWidth(self):
        if self.size:
            return self.size.width()

        return 0

    @pyqtSlot(result=int)
    def getHeight(self):
        if self.size:
            return self.size.height()

        return 0


class QMLApplicationWidget(QWidget):
    def __init__(self, fileUrl, parent=None):
        super(QMLApplicationWidget, self).__init__(parent=parent)

        self.stack = QStackedWidget()

        self.setLayout(QVBoxLayout())

        self.app = runningApp()
        self.epFileUrl = fileUrl

        self.fsw = FileWatcher(bufferMs=10000, delay=1, parent=self)
        self.fsw.pathChanged.connect(self.onReloadApp)
        self.fsw.watch(self.epFileUrl)

        self.layout().addWidget(self.stack)

        self.gInterface = GHandler(self)
        self.iInterface = IHandler(self)
        self.ldInterface = LDHandler(self)
        self.sparqlInterface = SparQLHandler(self)
        self.ipidInterface = IPIDHandler(self)
        self.ipfsInterface = IPFSHandler(self)
        self.ipfsInterface.psListen(keyPsJson)

        # Clone the IPFS profile
        self.webProfile = self.app.webProfiles['ipfs'].quickClone()

        self.engine = self.setupEngine()

    def onReloadApp(self, chPath):
        if self.app.debugEnabled:
            self.engine.clearComponentCache()
            self.load()

    def setupEngine(self):
        engine = QQmlEngine(self)
        ipfsCtx = self.app.ipfsCtx
        filesModel = ipfsCtx.currentProfile.filesModel

        ctx = engine.rootContext()

        ctx.setContextProperty('g', self.gInterface)
        ctx.setContextProperty('g_pronto', self.ldInterface)
        ctx.setContextProperty('g_sparql', self.sparqlInterface)
        ctx.setContextProperty('g_iContainer', self.iInterface)
        ctx.setContextProperty('g_ipid', self.ipidInterface)
        ctx.setContextProperty('g_ipfsop', self.ipfsInterface)

        srv = getByDotName('ld.pronto.rings')
        ctx.setContextProperty('g_pronto_pairing', srv.qtApi)

        # Pass the web profile
        ctx.setContextProperty('ipfsWebProfile', self.webProfile)

        ctx.setContextProperty('modelMfs', filesModel)

        return engine

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if self.stack.count() > 0:
            self.iInterface.size = event.size()
            self.iInterface.sizeChanged.emit(
                event.size().width(),
                event.size().height()
            )

    def importComponent(self, path):
        self.engine.addImportPath(path)
        self.fsw.watchWalk(Path(path))

    def onSceneGraphError(self, error, message: str):
        log.warning(f'Scene graph error ({error}): {message}')

    def load(self):
        current = self.stack.currentWidget()

        if isinstance(current, QQuickWidget) and \
                current.status != QQuickWidget.Null:
            disconnectSig(current.sceneGraphError, self.onSceneGraphError)

            current.deleteLater()
            self.stack.removeWidget(current)

        qcomp = quickEnginedWidget(
            self.engine,
            QUrl.fromLocalFile(self.epFileUrl)
        )

        if not qcomp:
            return

        qcomp.sceneGraphError.connect(self.onSceneGraphError)

        self.stack.addWidget(qcomp)
        self.stack.setCurrentWidget(qcomp)

        self.stack.setFocus(Qt.OtherFocusReason)
        qcomp.setFocus(Qt.OtherFocusReason)

        self.iInterface.size = self.size()
        self.iInterface.sizeChanged.emit(
            self.size().width(),
            self.size().height()
        )


def qmlRegisterCustomTypes():
    # Here's where we register custom types for the QML capsules

    qmlRegisterType(
        SparQLResultsModel,
        'Galacteek',
        1, 0,
        'SpQLModel'
    )
    qmlRegisterType(
        SparQLWrapperResultsModel,
        'Galacteek',
        1, 0,
        'SpQLEndpointModel'
    )
    qmlRegisterType(
        UnixFsDirModel,
        'Galacteek',
        1, 0,
        'UnixFsDirectoryModel'
    )
    qmlRegisterType(
        IPFSHandler,
        'Galacteek',
        1, 0,
        'GalacteekIpfsOperator'
    )
    qmlRegisterType(
        OntoloChainHandler,
        'Galacteek',
        1, 0,
        'OntologicalSideChain'
    )
    qmlRegisterType(
        RDFGraphHandler,
        'Galacteek',
        1, 0,
        'RDFGraphOperator'
    )
    qmlRegisterType(
        IpfsObjectInterface,
        'Galacteek',
        1, 0,
        'IpfsObject'
    )
