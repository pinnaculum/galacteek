from rdflib import Literal
from rdflib import XSD

from urllib.parse import unquote

from PyQt5.QtWidgets import QTreeView
from PyQt5.QtWidgets import QApplication

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QPoint
from PyQt5.QtCore import QRect
from PyQt5.QtCore import QRegExp
from PyQt5.QtCore import QSortFilterProxyModel

from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QToolTip

from PyQt5.QtCore import QModelIndex

from galacteek import services
from galacteek.core.models.sparql import hashmarks as models_hashmarks
from galacteek.ld.sparql import querydb


class HashmarksProxyModel(QSortFilterProxyModel):
    pass


class ContentSearchResultsTree(QTreeView):
    historyItemSelected = pyqtSignal(str)
    collapsed = pyqtSignal()

    def __init__(self, parent=None):
        super(ContentSearchResultsTree, self).__init__(parent=parent)

        self.setWindowFlag(Qt.Popup, True)
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.Tool, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_AlwaysShowToolTips)
        self.setWindowModality(Qt.NonModal)

        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Maximum
        )

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.app = QApplication.instance()
        self.setObjectName('graphSearchResultsTree')
        self.clicked.connect(self.onItemActivated)

        self.model = HashmarksProxyModel()
        self.model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.model.setFilterKeyColumn(0)

        self.setModel(self.model)
        self.setHeaderHidden(True)

        self.idxSelCount = 0
        self.selectionModel().currentChanged.connect(self.onIndexChanged)

    @property
    def pronto(self):
        return services.getByDotName('ld.pronto')

    @property
    def sourceModel(self):
        return self.pronto.allHashmarksItemModel

    @property
    def itemRoot(self):
        return self.model.invisibleRootItem()

    @property
    def resultsCount(self):
        return self.model.rowCount(QModelIndex())

    def onIndexChanged(self,
                       current: QModelIndex,
                       previous: QModelIndex) -> None:
        self.expand(current)
        self.collapse(previous)

        self.app.loop.call_later(
            0.1,
            QToolTip.showText,
            self.mapToGlobal(QPoint(0, self.height())),
            self.model.data(current, Qt.ToolTipRole),
            self,
            QRect(0, 0, 0, 0), 60000
        )

    def selectFirstItem(self):
        self.setCurrentIndex(self.model.index(0, 0, QModelIndex()))

    def onItemActivated(self, idx):
        idxUrl = self.model.index(idx.row(), 0, idx.parent())
        uri = self.model.data(idxUrl,
                              models_hashmarks.SubjectUriRole)

        if isinstance(uri, str) and uri:
            self.historyItemSelected.emit(unquote(uri))

    def getSparQlQuery(self, query='', mimeCategory='', keywords=[]):
        # Deprecated (was used when we used an isolated model)
        return (querydb.get('HashmarksSearchGroup'), {
            'searchQuery': Literal(query),
            'mimeCategoryQuery': Literal(mimeCategory),
            'limitn': Literal(100, datatype=XSD.integer),
            'langTagMatch': Literal('en')
        })

    def lookup(self, text: str):
        if not self.model.sourceModel():
            self.model.setSourceModel(self.sourceModel)

        self.model.setFilterRegExp(
            QRegExp(text.strip().replace(' ', '.*'),
                    Qt.CaseInsensitive,
                    QRegExp.RegExp)
        )

        # self.resizeColumnToContents(0)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return:
            # The 'activated' signal does not seem to have the same
            # behavior across platforms so we handle Return manually here
            curIdx = self.currentIndex()
            if curIdx.isValid():
                self.onItemActivated(curIdx)
        elif event.key() in [Qt.Key_Escape,
                             Qt.Key_Backspace]:
            self.hide()
            self.collapsed.emit()
        else:
            super(ContentSearchResultsTree, self).keyPressEvent(event)
