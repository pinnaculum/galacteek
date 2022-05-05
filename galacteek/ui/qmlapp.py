from pathlib import Path
from PyQt5.QtQml import QQmlEngine
from PyQt5.QtQml import qmlRegisterType
from PyQt5.QtQml import qmlRegisterSingletonType

from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QStackedWidget
from PyQt5.QtWidgets import QVBoxLayout

from PyQt5.QtCore import QUrl
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtCore import pyqtSlot

from galacteek.ipfs.wrappers import *

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

from galacteek.qml import *

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

    @pyqtSlot(result=int)
    def getHeight(self):
        if self.size:
            return self.size.height()

    def set_fake(self, *a):
        pass


class QMLApplicationWidget(QWidget):
    def __init__(self, fileUrl, parent=None):
        super(QMLApplicationWidget, self).__init__(parent=parent)

        self.setLayout(QVBoxLayout())

        self.app = runningApp()
        self.epFileUrl = fileUrl
        self.fsw = FileWatcher(parent=self)
        self.fsw.pathChanged.connect(self.onReloadApp)
        self.fsw.watch(self.epFileUrl)

        self.stack = QStackedWidget()
        self.layout().addWidget(self.stack)

        self.gInterface = GHandler(self)
        self.iInterface = IHandler(self)
        self.ldInterface = LDHandler(self)
        self.sparqlInterface = SparQLHandler(self)
        self.ipidInterface = IPIDHandler(self)
        self.ipfsInterface = IPFSHandler(self)
        self.ipfsInterface.psListen(keyPsJson)

        self.currentComponent = None

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

        # XML graph exports paths
        # ctx.setContextProperty('graphGXmlPath',
        #                        stores.graphG.xmlExportUrl)

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

        if 0:
            qmlRegisterSingletonType(
                SparQLSingletonResultsModel,
                'Galacteek',
                1, 0,
                'SpQLSingletonModel',
                createSparQLSingletonProxy
            )

        return engine

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if self.currentComponent:
            self.iInterface.size = event.size()
            self.iInterface.sizeChanged.emit(
                event.size().width(),
                event.size().height()
            )

    def importComponent(self, path):
        self.engine.addImportPath(path)
        self.fsw.watchWalk(Path(path))

    def load(self):
        if self.currentComponent:
            self.stack.removeWidget(self.currentComponent)
            self.currentComponent = None

        qcomp = quickEnginedWidget(
            self.engine,
            QUrl.fromLocalFile(self.epFileUrl),
            parent=self.stack
        )

        if not qcomp:
            return

        self.stack.addWidget(qcomp)
        self.stack.setCurrentWidget(qcomp)

        self.stack.setFocus(Qt.OtherFocusReason)
        qcomp.setFocus(Qt.OtherFocusReason)

        self.currentComponent = qcomp

        self.iInterface.size = self.size()
        self.iInterface.sizeChanged.emit(
            self.size().width(),
            self.size().height()
        )
