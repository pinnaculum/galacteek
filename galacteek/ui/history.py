
from PyQt5.QtWidgets import QListView
from PyQt5.QtWidgets import QApplication

from PyQt5.QtCore import QObject
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import Qt

from PyQt5.QtGui import QStandardItemModel
from PyQt5.QtGui import QStandardItem

from galacteek import ensure


class URLHistory(QObject):
    historyConfigChanged = pyqtSignal(bool)

    def __init__(self, db, enabled=False, parent=None):
        super(URLHistory, self).__init__(parent)
        self.db = db
        self.enabled = enabled
        self.historyConfigChanged.connect(self.onConfig)

    def onConfig(self, enableHistory):
        self.enabled = enableHistory

    def record(self, url, title):
        if self.enabled:
            ensure(self.db.historyRecord(url, title))

    def clear(self):
        ensure(self.db.historyClear())

    async def match(self, input):
        return await self.db.historySearch(input)


class HistoryMatchesWidget(QListView):
    historyItemSelected = pyqtSignal(str)
    collapsed = pyqtSignal()

    def __init__(self, parent=None):
        super(HistoryMatchesWidget, self).__init__(parent)

        self.app = QApplication.instance()
        self.setObjectName('historySearchResults')
        self.pressed.connect(self.onItemActivated)
        self.clicked.connect(self.onItemActivated)

        self.model = QStandardItemModel()
        self.setModel(self.model)

    def onItemActivated(self, idx):
        data = self.model.data(idx, Qt.EditRole)

        if isinstance(data, str):
            self.historyItemSelected.emit(data)

    def showMatches(self, matches):
        self.model.clear()
        for match in matches:
            if match['title']:
                text = '{title}: {url}'.format(
                    title=match['title'], url=match['url'])
            else:
                text = match['url']

            item = QStandardItem(text)
            item.setEditable(False)
            item.setData(match['url'], Qt.EditRole)
            self.model.invisibleRootItem().appendRow(item)

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
