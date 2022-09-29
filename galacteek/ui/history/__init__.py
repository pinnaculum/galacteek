from urllib.parse import unquote

from PyQt5.QtWidgets import QTreeView
from PyQt5.QtWidgets import QApplication

from PyQt5.QtCore import QObject
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import Qt

from PyQt5.QtGui import QStandardItemModel
from PyQt5.QtGui import QBrush
from PyQt5.QtGui import QColor
from PyQt5.QtGui import QFont

from galacteek import ensure
from galacteek import services
from galacteek.core.modelhelpers import UneditableItem
from galacteek import database
from galacteek.config import cGet


from ..i18n import iUnknown
from ..i18n import iHashmarks


class ResultCategoryItem(UneditableItem):
    pass


class URLHistory(QObject):
    historyConfigChanged = pyqtSignal(bool)

    @property
    def enabled(self):
        return cGet('enabled')

    def record(self, url, title):
        if self.enabled:
            ensure(database.urlHistoryRecord(url, title))

    def clear(self):
        ensure(database.urlHistoryClear())

    async def match(self, input):
        return await database.urlHistorySearch(input)


class HistoryMatchesWidget(QTreeView):
    historyItemSelected = pyqtSignal(str)
    collapsed = pyqtSignal()

    def __init__(self, parent=None):
        super(HistoryMatchesWidget, self).__init__(parent)

        self.setWindowFlag(Qt.Popup, True)
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.Tool, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowModality(Qt.NonModal)
        # self.setWindowModality(Qt.ApplicationModal)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.app = QApplication.instance()
        self.setObjectName('historySearchResults')
        self.clicked.connect(self.onItemActivated)

        self.hModel = QStandardItemModel()

        self.fontCategory = QFont('Times', 16, QFont.Bold)
        self.fontItems = QFont('Inter UI', 14)
        self.fontItemsTitle = QFont('Inter UI', 14, italic=True)
        self.setModel(self.hModel)
        self.setHeaderHidden(True)

        self.idxSelCount = 0
        self.selectionModel().currentChanged.connect(self.onIndexChanged)

    @property
    def pronto(self):
        return services.getByDotName('ld.pronto')

    @property
    def hAllModel(self):
        return self.pronto.allHashmarksModel

    @property
    def itemRoot(self):
        return self.hModel.invisibleRootItem()

    def onIndexChanged(self, current, previous):
        item = self.hModel.itemFromIndex(current)

        if isinstance(item, ResultCategoryItem) and self.idxSelCount == 0:
            # Automatically jump to first item in the category
            self.selectionModel().clearSelection()

            idx = self.hModel.index(0, 0, current)
            if idx.isValid():
                self.setCurrentIndex(idx)

        self.idxSelCount += 1

    def onItemActivated(self, idx):
        idxUrl = self.hModel.index(idx.row(), 1, idx.parent())
        data = self.hModel.data(idxUrl)

        if isinstance(data, str) and data:
            self.historyItemSelected.emit(data)

    async def lookup(self, text: str):
        self.expandAll()
        self.resizeColumnToContents(0)

    async def showMatches(self, marks, hMatches, hLdMatches):
        self.hModel.clear()
        brush = QBrush(QColor('#508cac'))

        mItem = ResultCategoryItem(iHashmarks())
        mItem.setFont(self.fontCategory)
        mItem.setBackground(brush)
        mItemE = UneditableItem('')
        mItemE.setBackground(brush)

        if len(marks) > 0:
            for match in marks:
                title = match.title[0:64] if match.title else iUnknown()

                url = match.preferredUrl()

                itemT = UneditableItem(title)
                itemT.setFont(self.fontItemsTitle)
                item = UneditableItem(url)
                item.setToolTip(url)
                item.setData(url, Qt.EditRole)
                item.setFont(self.fontItems)

                mItem.appendRow([itemT, item])

            self.hModel.invisibleRootItem().appendRow([mItem, mItemE])

        hItem = ResultCategoryItem('History')
        hItemE = UneditableItem('')
        hItem.setFont(self.fontCategory)
        hItem.setBackground(brush)
        hItemE.setBackground(brush)

        if len(hMatches) > 0 and 0:  # XXX
            for match in hMatches:

                title = str(match['title'])[0:64]
                itemT = UneditableItem(title)
                itemT.setFont(self.fontItemsTitle)

                item = UneditableItem(match['url'])
                item.setToolTip(match['url'])
                item.setData(match['url'], Qt.EditRole)
                item.setFont(self.fontItems)

                hItem.appendRow([itemT, item])

            self.hModel.invisibleRootItem().appendRow([hItem, hItemE])

        if len(hLdMatches) > 0:
            # Show RDF hashmarks

            for match in hLdMatches:
                # URI ref is urlencoded
                uri = unquote(str(match['uri']))

                title = str(match['title'])[0:64]
                itemT = UneditableItem(title)
                itemT.setFont(self.fontItemsTitle)

                item = UneditableItem(uri)
                item.setToolTip(uri)
                item.setData(uri, Qt.EditRole)
                item.setFont(self.fontItems)

                mItem.appendRow([itemT, item])

            self.hModel.invisibleRootItem().appendRow([mItem, mItemE])

        self.expandAll()
        self.resizeColumnToContents(0)

    def hideEvent(self, event):
        self.idxSelCount = 0
        super().hideEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return:
            # The 'activated' signal does not seem to have the same
            # behavior across platforms so we handle Return manually here
            curIdx = self.currentIndex()
            if curIdx.isValid():
                self.onItemActivated(curIdx)
        elif event.key() == Qt.Key_Escape:
            self.hide()
            self.collapsed.emit()
        else:
            super(HistoryMatchesWidget, self).keyPressEvent(event)
