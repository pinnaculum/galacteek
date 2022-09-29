import functools
from rdflib import Literal

from PyQt5.QtWidgets import QAbstractItemView
from PyQt5.QtWidgets import QHeaderView
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QTreeView
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QComboBox
from PyQt5.QtWidgets import QMenu
from PyQt5.QtWidgets import QToolButton
from PyQt5.QtWidgets import QStyledItemDelegate

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QSize
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import pyqtSignal

from galacteek import ensure
from galacteek import services
from galacteek import partialEnsure
from galacteek.core import runningApp
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ui.widgets import GalacteekTab
from galacteek.ui.widgets import AnimatedLabel
from galacteek.ui.clips import RotatingCubeRedFlash140d
from galacteek.ui.helpers import getIcon
from galacteek.ui.helpers import BasicKeyFilter

from galacteek.ui.clipboard import iCopyPathToClipboard

from galacteek.core.models.sparql.hashmarks import LDHashmarksSparQLItemModel
from galacteek.core.models.sparql.hashmarks import HashmarkUriRole

from galacteek.ld.sparql import querydb


class HashmarkDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        option.decorationSize = QSize(32, 32)

        super().paint(painter, option, index)


class HashmarksView(QTreeView):
    def __init__(self, parent=None):
        super(HashmarksView, self).__init__(parent=parent)

        self.delegate = HashmarkDelegate()
        self.setItemDelegate(self.delegate)

        self.evFilter = BasicKeyFilter()
        self.evFilter.returnPressed.connect(self.onReturnPressed)
        # self.installEventFilter(self.evFilter)

        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setHeaderHidden(True)

        # self.setObjectName('hashmarksTreeView')

    def onReturnPressed(self):
        pass

    def dragMoveEvent(self, event):
        event.accept()

    def dragEnterEvent(self, event):
        event.accept()


class SearchLine(QLineEdit):
    downPressed = pyqtSignal()

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Down:
            self.downPressed.emit()

        super().keyPressEvent(ev)


class HashmarksCenterWidget(GalacteekTab):
    def __init__(self, mainW, parent=None):
        super(HashmarksCenterWidget, self).__init__(mainW, parent=parent)

        self.app = runningApp()
        self.model = LDHashmarksSparQLItemModel(
            graphUri='urn:ipg:i:love:hashmarks',
            columns=['Title', 'MIME']
        )

        self.editTimer = QTimer(self)
        self.editTimer.setSingleShot(True)
        self.editTimer.timeout.connect(partialEnsure(self.runQuery))

        self.helpButton = QToolButton()
        self.helpButton.setIcon(getIcon('help.png'))
        self.helpButton.setMinimumSize(QSize(32, 32))
        self.helpButton.clicked.connect(self.onHelp)

        self.cube = AnimatedLabel(
            RotatingCubeRedFlash140d(speed=100),
        )
        self.cube.clip.setScaledSize(QSize(32, 32))

        self.cLayout = QHBoxLayout()
        self.vLayout.addLayout(self.cLayout)

        self.comboMime = QComboBox()
        self.comboMime.addItem('.*')
        self.comboMime.addItem('application')
        self.comboMime.addItem('audio')
        self.comboMime.addItem('image')
        self.comboMime.addItem('text')
        self.comboMime.addItem('inode')
        self.comboMime.addItem('multipart')
        self.comboMime.addItem('video')
        self.comboMime.currentIndexChanged.connect(
            partialEnsure(self.onSearch))

        self.comboResultsLimit = QComboBox()

        for x in range(50, 1500, 50):
            self.comboResultsLimit.addItem(str(x))

        self.comboResultsLimit.setCurrentText(str(250))
        self.comboResultsLimit.currentIndexChanged.connect(
            partialEnsure(self.onSearch))

        self.searchLine = SearchLine()
        # self.searchLine.returnPressed.connect(partialEnsure(self.onSearch))
        # self.searchLine.textEdited.connect(partialEnsure(self.onSearch))
        self.searchLine.textEdited.connect(self.onSearchEdit)
        self.searchLine.downPressed.connect(self.onDownKey)

        self.cLayout.addWidget(self.helpButton)
        self.cLayout.addWidget(QLabel('Search'))
        self.cLayout.addWidget(self.searchLine)
        self.cLayout.addWidget(QLabel('MIME category'))
        self.cLayout.addWidget(self.comboMime)
        self.cLayout.addWidget(QLabel('Max results'))
        self.cLayout.addWidget(self.comboResultsLimit)
        self.cLayout.addWidget(self.cube)

        self.treeV = HashmarksView(self)
        self.treeV.setModel(self.model)
        self.treeV.setContextMenuPolicy(Qt.CustomContextMenu)
        self.treeV.header().setSectionResizeMode(
            QHeaderView.ResizeToContents)
        self.treeV.setHeaderHidden(True)

        self.treeV.customContextMenuRequested.connect(self.onContextMenu)
        self.treeV.doubleClicked.connect(
            partialEnsure(self.onMarkDoubleClicked))
        self.treeV.evFilter.returnPressed.connect(self.onTreeReturnPressed)

        self.addToLayout(self.treeV)

        self.searchLine.setFocus(Qt.OtherFocusReason)

    @property
    def icapsuledb(self):
        return services.getByDotName('core.icapsuledb')

    def onHelp(self):
        self.app.manuals.browseManualPage('hashmarks.html',
                                          fragment='rdf-hashmarks-store')

    def onContextMenu(self, point):
        idx = self.treeV.indexAt(point)
        path = IPFSPath(
            self.model.data(idx, HashmarkUriRole)
        )

        if not path.valid:
            return

        menu = QMenu(self)
        menu.addAction(
            getIcon('clipboard.png'),
            iCopyPathToClipboard(),
            functools.partial(self.app.setClipboardText, str(path))
        )

        menu.exec(self.treeV.mapToGlobal(point))

    def refresh(self):
        self.searchLine.setFocus(Qt.OtherFocusReason)

    def onDownKey(self):
        self.treeV.setFocus(Qt.OtherFocusReason)

    def onSearchEdit(self, text):
        self.editTimer.stop()
        self.editTimer.start(500)

    async def onSearch(self, *args):
        self.editTimer.stop()
        await self.runQuery()

    async def runQuery(self):
        q, bindings = self.getSparQlQuery(
            query=self.searchLine.text().strip(),
            mimeCategory=self.comboMime.currentText(),
            keywords=self.searchLine.text().split()
        )

        self.cube.startClip()
        self.cube.clip.setSpeed(150)

        self.model.clearModel()

        await self.model.graphBuild(q, bindings)

        self.model.modelReset.emit()

        self.cube.stopClip()

    def onTreeReturnPressed(self):
        idx = self.treeV.currentIndex()
        if idx.isValid():
            ensure(self.onMarkDoubleClicked(idx))

    async def onMarkDoubleClicked(self, index):
        path = IPFSPath(
            self.model.data(index, HashmarkUriRole)
        )

        if path.valid:
            await self.app.resourceOpener.open(path)

    def getSparQlQuery(self, query='', mimeCategory='.*', keywords=[]):
        return (querydb.get('HashmarksSearchGroup'), {
            'searchQuery': Literal(query),
            'mimeCategoryQuery': Literal(mimeCategory),
            'limitn': int(self.comboResultsLimit.currentText()),
            'langTagMatch': Literal('en')
        })
