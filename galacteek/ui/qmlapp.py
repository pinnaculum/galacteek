from pathlib import Path
from PyQt5.QtQml import QQmlEngine

from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QStackedWidget
from PyQt5.QtWidgets import QVBoxLayout

from PyQt5.QtPrintSupport import *

from PyQt5.QtCore import QUrl
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtCore import pyqtSlot

from galacteek.ipfs.wrappers import *

from galacteek.dweb.channels.g import GHandler
from galacteek.dweb.channels.ld import LDHandler
from galacteek.dweb.channels.sparql import SparQLHandler
from galacteek.dweb.channels.ipid import IPIDHandler

from galacteek.qml import *

from .helpers import *
from .dialogs import *
from .i18n import *
from .widgets import *

from galacteek.core import runningApp
from galacteek.core.models.iquick import *
from galacteek.core.fswatcher import FileWatcher


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

        self.currentComponent = None

        # Clone the IPFS profile
        self.webProfile = self.app.webProfiles['ipfs'].quickClone()

        # TODO: move this in global place
        self.models = {
            'Articles': ArticlesModel(),
            'Channels': MultimediaChannelsModel(),
            'Shouts': ShoutsModel()
        }
        self.setupEngine()

    @property
    def comp(self):
        return self.currentComponent

    def onReloadApp(self, chPath):
        print(chPath, 'changed')

        self.engine.clearComponentCache()
        self.load()

    def setupEngine(self):
        ipfsCtx = self.app.ipfsCtx
        filesModel = ipfsCtx.currentProfile.filesModel

        # stores = services.getByDotName('ld.rdf.graphs')

        self.engine = QQmlEngine(self)
        ctx = self.engine.rootContext()

        # XML graph exports paths
        # ctx.setContextProperty('graphGXmlPath',
        #                        stores.graphG.xmlExportUrl)

        ctx.setContextProperty('g', self.gInterface)
        ctx.setContextProperty('ld', self.ldInterface)
        ctx.setContextProperty('sparql', self.sparqlInterface)
        ctx.setContextProperty('iContainer', self.iInterface)
        ctx.setContextProperty('ipid', self.ipidInterface)

        # Pass the web profile
        ctx.setContextProperty('ipfsWebProfile', self.webProfile)

        ctx.setContextProperty('modelArticles',
                               self.models['Articles'])
        ctx.setContextProperty('modelMultiChannels',
                               self.models['Channels'])
        ctx.setContextProperty('modelShouts',
                               self.models['Shouts'])
        ctx.setContextProperty('modelMfs', filesModel)

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if self.comp:
            self.iInterface.size = event.size()
            self.iInterface.sizeChanged.emit(
                event.size().width(),
                event.size().height()
            )

    def importComponent(self, path):
        self.engine.addImportPath(path)
        self.fsw.watchWalk(Path(path))

    def load(self):
        # stores = services.getByDotName('ld.rdf.graphs')
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
