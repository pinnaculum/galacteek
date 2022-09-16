import functools
from rdflib import Literal

from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QListView
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QComboBox
from PyQt5.QtWidgets import QMenu
from PyQt5.QtWidgets import QToolButton

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QSize

from galacteek import services
from galacteek import partialEnsure
from galacteek.core import runningApp
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ui.widgets import GalacteekTab
from galacteek.ui.widgets import AnimatedLabel
from galacteek.ui.clips import RotatingCubeRedFlash140d
from galacteek.ui.helpers import getIcon

from galacteek.ui.clipboard import iCopyPathToClipboard

from galacteek.core.models.sparql.hashmarks import LDHashmarksSparQLListModel
from galacteek.core.models.sparql.hashmarks import HashmarkUriRole

from galacteek.ld.sparql import querydb


class HashmarksView(QListView):
    def __init__(self, parent=None):
        super(HashmarksView, self).__init__(parent=parent)

        self.setObjectName('hashmarksListView')


class HashmarksCenterWidget(GalacteekTab):
    def __init__(self, mainW, parent=None):
        super(HashmarksCenterWidget, self).__init__(mainW, parent=parent)

        self.app = runningApp()
        self.model = LDHashmarksSparQLListModel(
            graphUri='urn:ipg:i:love:hashmarks'
        )

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
        self.comboMime.addItem('*')
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

        self.searchLine = QLineEdit()
        self.searchLine.returnPressed.connect(partialEnsure(self.onSearch))

        self.cLayout.addWidget(self.helpButton)
        self.cLayout.addWidget(QLabel('Search'))
        self.cLayout.addWidget(self.searchLine)
        self.cLayout.addWidget(QLabel('MIME category'))
        self.cLayout.addWidget(self.comboMime)
        self.cLayout.addWidget(QLabel('Max results'))
        self.cLayout.addWidget(self.comboResultsLimit)
        self.cLayout.addWidget(self.cube)

        self.listW = HashmarksView(self)
        self.listW.setModel(self.model)
        self.listW.setContextMenuPolicy(Qt.CustomContextMenu)
        self.listW.customContextMenuRequested.connect(self.onContextMenu)
        self.listW.doubleClicked.connect(
            partialEnsure(self.onMarkDoubleClicked))

        self.addToLayout(self.listW)

        self.searchLine.setFocus(Qt.OtherFocusReason)

    @property
    def icapsuledb(self):
        return services.getByDotName('core.icapsuledb')

    def onHelp(self):
        self.app.manuals.browseManualPage('hashmarks.html',
                                          fragment='rdf-hashmarks-store')

    def onContextMenu(self, point):
        idx = self.listW.indexAt(point)
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

        menu.exec(self.listW.mapToGlobal(point))

    def refresh(self):
        self.searchLine.setFocus(Qt.OtherFocusReason)

    async def onSearch(self, *args):
        await self.runQuery()

    async def runQuery(self):
        q, bindings = self.hMarksQuery(
            mimeCategory=self.comboMime.currentText(),
            keywords=self.searchLine.text().split()
        )

        self.cube.startClip()
        self.cube.clip.setSpeed(150)

        self.model.clearModel()
        await self.model.graphQueryAsync(q, bindings)

        self.cube.stopClip()

    async def onMarkDoubleClicked(self, index):
        path = IPFSPath(
            self.model.data(index, HashmarkUriRole)
        )

        if path.valid:
            await self.app.resourceOpener.open(path)

    def hMarksQuery(self, mimeCategory='*', keywords=[]):
        bindings = {'langTagMatch': Literal('en')}

        titlesf, mimef = '', ''
        titlesc = []

        for kw in keywords:
            titlesc.append(f'contains(str(?title), "{kw}")\n')

        if titlesc:
            titlesf = 'FILTER( ' + '&&'.join(titlesc) + ' )'

        if mimeCategory != '*':
            mimef += f'FILTER(str(?mimeCategory) = "{mimeCategory}")'

        limitn = self.comboResultsLimit.currentText()
        query = querydb.get(
            'HashmarksSearchGroup',
            titlesf, mimef, limitn
        )

        return query, bindings
