
import sys

from PyQt5.QtWidgets import QWidget, QTreeView, QMenu
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import QCoreApplication, QUrl, Qt, QObject

from . import ui_bookmarksmgr
from .modelhelpers import *
from .helpers import *
from .dialogs import *
from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.cidhelpers import *

def iPath():
    return QCoreApplication.translate('BookmarksViewForm', 'Path')

def iTitle():
    return QCoreApplication.translate('BookmarksViewForm', 'Title')

def iDate():
    return QCoreApplication.translate('BookmarksViewForm', 'Date')

def iAlreadyBookmarked():
    return QCoreApplication.translate('BookmarksViewForm',
        'Already Bookmarked')

class BookmarksView(QTreeView): pass

class BookmarksModel(QStandardItemModel):
    def itemChanged(item):
        print(item, 'changed')

def addBookmark(bookmarks, path, title):
    if bookmarks.search(path=path):
        return messageBox(iAlreadyBookmarked())

    dlg = AddBookmarkDialog(bookmarks, path, title)
    dlg.exec_()
    dlg.show()
    return

class BookmarksTab(GalacteekWidget):
    def __init__(self, gWindow, parent=None):
        super().__init__(parent=parent)

        self.gWindow = gWindow
        self.bookmarks = gWindow.getApp().bookmarks
        self.bookmarks.changed.connect(self.updateTree)

        self.ui = ui_bookmarksmgr.Ui_BookmarksViewForm()
        self.ui.setupUi(self)
        icon1 = getIcon('bookmarks.png')
        self.ui.toolbox.setItemIcon(0, icon1)

        self.ui.bookmarksBox.insertItem(0, 'Bookmark as IPFS')
        self.ui.bookmarksBox.setItemIcon(0, icon1)
        self.ui.bookmarksBox.activated.connect(self.onBoxActivated)

        self.model = BookmarksModel()
        self.model.setHorizontalHeaderLabels([iPath(), iTitle()])

        self.tree = self.ui.bookmarksTree

        self.tree.setColumnWidth(0, 600)
        self.tree.resizeColumnToContents(0)
        self.tree.doubleClicked.connect(self.onItemDoubleClicked)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.onContextMenu)
        self.tree.setModel(self.model)

        self.updateTree()

    def onBoxActivated(self, idx):
        mark = self.ui.bookmarkLine.text()

        if idx == 0:
            if not isMultihash(mark):
                return messageBox('Invalid input')

            if not mark.startswith('/ipfs'):
                mark = joinIpfs(mark)
            addBookmark(self.bookmarks, mark, '')
        self.ui.bookmarkLine.clear()

    def onDataChanged(self, top, bottom):
        pass

    def updateTree(self):
        categories = self.bookmarks.getCategories()

        for cat in categories:
            catItem = None
            ret = modelSearch(self.model, search=cat)
            if not ret:
                item1 = QStandardItem(cat)
                item2 = QStandardItem('')
                self.model.invisibleRootItem().appendRow([item1, item2])
                catItem = item1
            else:
                catItem = self.model.itemFromIndex(ret[0])

            catItemIdx = self.model.indexFromItem(catItem)

            marks = self.bookmarks.getForCategory(cat)
            for bm in marks:
                path = bm.get('path', None)
                if not path:
                    continue

                ret = modelSearch(self.model, search=path)
                if ret: continue

                item1 = QStandardItem(path)
                item2 = QStandardItem(bm['title'] or 'Unknown')

                item1.setEditable(False)
                item2.setEditable(True)
                catItem.appendRow([item1, item2])

            self.tree.expand(catItemIdx)

        self.tree.resizeColumnToContents(0)

    def onContextMenu(self, point):
        idx = self.tree.indexAt(point)
        if not idx.isValid():
            return

        idxPath = self.model.sibling(idx.row(), 0, idx)
        dataPath = self.model.data(idxPath)
        menu = QMenu()

        def remove(path):
            if self.bookmarks.delete(path):
                modelDelete(self.model, path)

        act2 = menu.addAction('Remove', lambda:
                remove(dataPath))
        menu.exec(self.tree.mapToGlobal(point))

    def onItemDoubleClicked(self, index):
        indexPath = self.model.sibling(index.row(), 0, index)
        path = self.model.data(indexPath)
        tab = self.gWindow.addBrowserTab()
        tab.browseFsPath(path)
