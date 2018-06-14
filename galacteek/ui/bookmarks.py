
import sys
import asyncio
from datetime import datetime

from PyQt5.QtWidgets import QWidget, QTreeView, QMenu, QHeaderView, QAction
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import QCoreApplication, QUrl, Qt, QObject, QDateTime

from . import ui_bookmarksmgr, ui_bookmarksmgrnetwork, ui_bookmarksmgrfeeds
from .modelhelpers import *
from .helpers import *
from .dialogs import *
from .widgets import *
from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.cidhelpers import *

def iPath():
    return QCoreApplication.translate('BookmarksViewForm', 'Path')

def iTitle():
    return QCoreApplication.translate('BookmarksViewForm', 'Title')

def iShared():
    return QCoreApplication.translate('BookmarksViewForm', 'Shared')

def iDate():
    return QCoreApplication.translate('BookmarksViewForm', 'Date')

def iTimestamp():
    return QCoreApplication.translate('BookmarksViewForm', 'Timestamp')

def iAlreadyBookmarked():
    return QCoreApplication.translate('BookmarksViewForm',
        'Already Bookmarked')

def iImportBookmark():
    return QCoreApplication.translate('BookmarksViewForm',
        'Import bookmark to')

def iNetworkMarks():
    return QCoreApplication.translate('BookmarksViewForm', 'Network hashmarks')

def iFeeds():
    return QCoreApplication.translate('BookmarksViewForm', 'Feeds')

class BookmarksView(QTreeView): pass

class BookmarksModel(QStandardItemModel):
    pass

class FeedsModel(QStandardItemModel):
    pass

class CategoryItem(UneditableItem):
    pass

def addBookmark(bookmarks, path, title, stats={}):
    if bookmarks.search(path):
        return messageBox(iAlreadyBookmarked())

    runDialog(AddBookmarkDialog, bookmarks, path, title, stats)

class _MarksUpdater:
    def __init__(self):
        self.updatingMarks = False
        self._marksCache = []

    async def updateMarks(self, model, marks, tree, parent=None):
        if self.updatingMarks == True:
            return

        self.updatingMarks = True

        if parent is None:
            parent = model.invisibleRootItem()

        abQuery = marks.asyncQ
        categories = await abQuery.getCategories()

        for cat in categories:
            catItem = None
            ret = await modelSearchAsync(model,
                    parent=parent.index(),
                    maxdepth=1,
                    search=cat, columns=[0])
            if len(ret) == 0:
                catItem = CategoryItem(cat)
                parent.appendRow([catItem])
            else:
                catItem = model.itemFromIndex(ret[0])

            catItemIdx = model.indexFromItem(catItem)
            tree.expand(catItemIdx)

            marks = await abQuery.getCategoryMarks(cat)
            for path, bm in marks.items():
                if path in self._marksCache:
                    continue

                item1 = UneditableItem(path)
                item2 = UneditableItem(bm['metadata']['title'] or 'Unknown')
                item3 = UneditableItem('yes' if bm['share'] is True else 'no')
                dt = QDateTime.fromString(bm['datecreated'], Qt.ISODate)
                item4 = UneditableItem(dt.toString())
                item5 = UneditableItem(str(bm['tscreated']))
                catItem.appendRow([item1, item2, item3, item4, item5])

                self._marksCache.append(path)

        self.updatingMarks = False
        tree.sortByColumn(4, Qt.DescendingOrder)
        tree.setSortingEnabled(True)

class FeedsView(QWidget):
    def __init__(self, marksTab, marks, loop, parent=None):
        super().__init__(parent)

        self.marksTab = marksTab
        self.loop = loop
        self.marks = marks

        self.ui = ui_bookmarksmgrfeeds.Ui_FeedsViewForm()
        self.ui.setupUi(self)

        self.marks.changed.connect(self.updateFeeds)
        self.tree = self.ui.treeFeeds
        self.model = FeedsModel()
        self.model.setHorizontalHeaderLabels([iPath(), iTitle(), iDate()])
        self.tree.setModel(self.model)
        self.tree.doubleClicked.connect(self.onFeedDoubleClick)
        self.tree.setSortingEnabled(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)

        self.updateFeeds()

    def updateFeeds(self):
        parent = self.model.invisibleRootItem()
        feeds = self.marks.getFeeds()

        for fPath, fData in feeds.items():
            fItem = None
            ret = modelSearch(self.model, parent=parent.index(),
                    search=fPath, columns=[0])
            if not ret:
                feedName = fData['name']
                if not feedName:
                    feedName = fPath
                fItem = UneditableItem(feedName)
                parent.appendRow([fItem])
            else:
                fItem = self.model.itemFromIndex(ret[0])

            fItemIdx = self.model.indexFromItem(fItem)
            self.ui.treeFeeds.expand(fItemIdx)

            marks = self.marks.getFeedMarks(fPath)
            for mPath, mData in marks.items():
                ret = modelSearch(self.model, parent=parent.index(),
                        search=mPath, columns=[0])
                if ret: continue

                item1 = UneditableItem(mPath)
                dt = QDateTime.fromString(mData['datecreated'],
                        Qt.ISODate)
                fItem.appendRow([item1,
                    UneditableItem(mData['metadata']['title']),
                    UneditableItem(dt.toString())
                ])

        self.tree.sortByColumn(2, Qt.DescendingOrder)
        self.tree.setSortingEnabled(True)

    def onFeedDoubleClick(self, index):
        indexPath = self.model.sibling(index.row(), 0, index)
        path = self.model.data(indexPath)
        if path:
            self.marksTab.gWindow.addBrowserTab().browseFsPath(path)

class NetworkMarksView(QWidget, _MarksUpdater):
    def __init__(self, marksTab, marks, marksLocal, loop, parent=None):
        super().__init__(parent)

        self.marksTab = marksTab
        self.loop = loop
        self.marks = marks
        self.marksLocal = marksLocal

        self.ui = ui_bookmarksmgrnetwork.Ui_NetworkMarksViewForm()
        self.ui.setupUi(self)
        self.ui.search.returnPressed.connect(self.onSearch)
        self.ui.searchButton.clicked.connect(self.onSearch)

        self.model = BookmarksModel()
        self.model.setHorizontalHeaderLabels([iPath(), iTitle(), iShared(),
            iDate(), iTimestamp()])

        self.tree = self.ui.treeNetMarks
        self.tree.setModel(self.model)
        self.tree.doubleClicked.connect(self.onDoubleClick)
        self.tree.header().setSectionResizeMode(0,
                QHeaderView.ResizeToContents)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.onContextMenu)

        self.marks.changed.connect(self.doMarksUpdate)

        self.doMarksUpdate()

    def onContextMenu(self, point):
        idx = self.tree.indexAt(point)
        if not idx.isValid():
            return

        idxPath = self.model.sibling(idx.row(), 0, idx)
        dataPath = self.model.data(idxPath)

        localCategories = self.marksLocal.getCategories()
        menu = QMenu()
        catsMenu = QMenu(iImportBookmark())

        def importMark(action):
            cat = action.data()['category']
            mark = action.data()['mark']

            r = self.marksLocal.insertMark(mark, cat)

        mark = self.marks.search(dataPath)
        for cat in localCategories:
            action = QAction(cat, self)
            action.setData({
                'category': cat,
                'mark': mark
            })
            catsMenu.addAction(action)
        catsMenu.triggered.connect(importMark)

        menu.addMenu(catsMenu)
        menu.exec(self.tree.mapToGlobal(point))

    def doMarksUpdate(self):
        self.loop.create_task(self.updateMarks(
            self.model, self.marks, self.tree))

    def onSearch(self):
        text = self.ui.search.text()
        ret = modelSearch(self.model, searchre=text, columns=[0,1])
        if len(ret) > 0:
            idx = ret.pop()
            self.tree.scrollTo(idx)
            self.tree.setCurrentIndex(idx)

    def onDoubleClick(self, index):
        indexPath = self.model.sibling(index.row(), 0, index)
        path = self.model.data(indexPath)
        if path:
            self.marksTab.gWindow.addBrowserTab().browseFsPath(path)

class BookmarksTab(GalacteekTab, _MarksUpdater):
    def __init__(self, *args, **kw):
        super(BookmarksTab, self).__init__(*args, **kw)

        self.marksLocal = self.app.marksLocal
        self.marksNetwork = self.app.marksNetwork

        self.marksLocal.changed.connect(self.doMarksUpdate)
        self.marksLocal.markDeleted.connect(self.onMarkDeleted)

        self.ui = ui_bookmarksmgr.Ui_BookmarksViewForm()
        self.ui.setupUi(self)

        self.uiNet = NetworkMarksView(self, self.marksNetwork,
                self.marksLocal, self.loop, parent=self)
        self.uiFeeds = FeedsView(self, self.marksLocal,
                self.loop, parent=self)
        self.ui.toolbox.addItem(self.uiNet, iNetworkMarks())
        self.ui.toolbox.addItem(self.uiFeeds, iFeeds())

        self.filter = BasicKeyFilter()
        self.filter.deletePressed.connect(self.onDeletePressed)
        self.installEventFilter(self.filter)

        icon1 = getIcon('bookmarks.png')
        self.ui.toolbox.setItemIcon(0, icon1)
        self.ui.toolbox.setItemIcon(1, icon1)

        self.modelMarks = BookmarksModel()
        self.modelMarks.setHorizontalHeaderLabels([iPath(), iTitle(),
            iShared(), iDate()])
        self.ui.treeMarks.setModel(self.modelMarks)

        self.ui.treeMarks.header().setSectionResizeMode(0,
                QHeaderView.ResizeToContents)
        self.ui.treeMarks.doubleClicked.connect(self.onMarkItemDoubleClick)
        self.ui.treeMarks.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.treeMarks.customContextMenuRequested.connect(self.onContextMenu)

        self.updatingMarks = False
        self.doMarksUpdate()

    def onBoxActivated(self, idx):
        mark = self.ui.bookmarkLine.text()

        if idx == 0:
            if not cidValid(mark):
                return messageBox('Invalid input')

            if not mark.startswith('/ipfs'):
                mark = joinIpfs(mark)
            addBookmark(self.marksLocal, mark, '')
        self.ui.bookmarkLine.clear()

    def onMarkDeleted(self, mPath):
        if mPath in self._marksCache:
            self._marksCache.remove(mPath)

    def doMarksUpdate(self):
        self.loop.create_task(self.updateMarks(
            self.modelMarks, self.marksLocal, self.ui.treeMarks))

    def onContextMenu(self, point):
        idx = self.ui.treeMarks.indexAt(point)
        if not idx.isValid():
            return

        idxPath = self.modelMarks.sibling(idx.row(), 0, idx)
        dataPath = self.modelMarks.data(idxPath)
        menu = QMenu()

        act2 = menu.addAction('Delete', lambda:
                self.deleteMark(dataPath))
        menu.exec(self.ui.treeMarks.mapToGlobal(point))

    def deleteMark(self, path):
        if self.marksLocal.delete(path):
            modelDelete(self.modelMarks, path)

    def currentItemPath(self):
        idx = self.ui.treeMarks.currentIndex()
        item = self.modelMarks.itemFromIndex(idx)

        if type(item) is CategoryItem:
            return None

        return self.modelMarks.data(
            self.modelMarks.sibling(idx.row(), 0, idx))

    def onDeletePressed(self):
        path = self.currentItemPath()
        if path:
            self.deleteMark(path)

    def onMarkItemChangeShare(self, index, path):
        shareItem = self.modelMarks.itemFromIndex(index)
        markSearch = self.marksLocal.search(path)
        if markSearch:
            path, mark = markSearch
            if mark['share'] is True:
                mark['share'] = False
                shareItem.setText('no')
            elif mark['share'] is False:
                mark['share'] = True
                shareItem.setText('yes')
            self.marksLocal.changed.emit()

    def onMarkItemDoubleClick(self, index):
        indexPath = self.modelMarks.sibling(index.row(), 0, index)
        item0 = self.modelMarks.itemFromIndex(indexPath)
        path = self.modelMarks.data(indexPath)

        if index.column() == 2:
            return self.onMarkItemChangeShare(index, path)

        if type(item0) is CategoryItem:
            return

        tab = self.gWindow.addBrowserTab()
        tab.browseFsPath(path)
