
from PyQt5.QtWidgets import QListView
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItemModel
from PyQt5.QtGui import QStandardItem

from galacteek import ensure


class URLHistory:
    def __init__(self, db, enabled=True):
        self.db = db
        self.enabled = enabled

    def record(self, url, title):
        if self.enabled:
            ensure(self.db.historyRecord(url, title))

    async def match(self, input):
        return await self.db.historySearch(input)


class HistoryMatchesWidget(QListView):
    historyItemSelected = pyqtSignal(str)
    collapsed = pyqtSignal()

    def __init__(self, parent=None):
        super(HistoryMatchesWidget, self).__init__(parent)

        self.setObjectName('historySearchResults')
        self.activated.connect(self.onItemActivated)
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
        if event.key() == Qt.Key_Escape:
            self.hide()
            self.collapsed.emit()

        super(HistoryMatchesWidget, self).keyPressEvent(event)
