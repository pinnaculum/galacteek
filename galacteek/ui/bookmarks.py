
import sys

from PyQt5.QtWidgets import QWidget, QMainWindow, QTextEdit, QVBoxLayout, QAction
from PyQt5.QtWidgets import QTreeView

from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import QUrl, Qt, pyqtSlot

from .modelhelpers import *

class BookmarksView(QTreeView): pass

class BookmarksTab(QWidget):
    def __init__(self, gWindow, parent=None):
        super(QWidget, self).__init__(parent=parent)

        self.gWindow = gWindow
        self.app = gWindow.getApp()
        self.app.bookmarks.changed.connect(self.updateTree)

        self.vLayout = QVBoxLayout(self)

        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(['Path', 'Title'])

        self.tree = BookmarksView()
        self.tree.setColumnWidth(0, 600)
        self.tree.resizeColumnToContents(0)
        self.tree.doubleClicked.connect(self.onItemDoubleClicked)
        self.tree.setModel(self.model)
        self.vLayout.addWidget(self.tree)

        self.updateTree()

    def updateTree(self):
        marks = self.app.bookmarks.getForCategory('main')

        for bm in marks:
            ret = modelSearch(self.model, search=bm['url'])
            if ret:
                continue
            item1 = QStandardItem(bm['url'])
            item2 = QStandardItem(bm['title'])
            item1.setEditable(False)
            item2.setEditable(False)
            self.model.appendRow([item1, item2])

        self.tree.resizeColumnToContents(0)

    def onItemDoubleClicked(self, index):
        row = index.row()
        url = self.model.data(self.model.index(row, 0))
        tab = self.gWindow.addBrowserTab()
        tab.browseFsPath(url)
