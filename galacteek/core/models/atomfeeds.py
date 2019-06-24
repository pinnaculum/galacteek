from PyQt5.QtWidgets import QApplication

from PyQt5.QtGui import QStandardItemModel

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QModelIndex
from PyQt5.QtCore import QObject

from galacteek import ensure
from galacteek.core.modelhelpers import *
from galacteek.ui.i18n import *  # noqa
from galacteek.ui.helpers import *

from galacteek.ui.i18n import iUnknown


class BaseItem(UneditableItem):
    def __init__(self, text, icon=None):
        super(BaseItem, self).__init__(text, icon=icon)

    def childrenItems(self):
        for row in range(0, self.rowCount()):
            child = self.child(row, 0)
            if child:
                yield child

    def findChildByName(self, name):
        for item in self.childrenItems():
            if not isinstance(item, str):
                continue
            if item.entry['Name'] == name:
                return item


class AtomFeedEntryItem(BaseItem):
    def __init__(self, entry, icon=None):
        self.entry = entry
        super(AtomFeedEntryItem, self).__init__(self.entry.title,
                                                icon=icon)

        self.setToolTip(self.entry.id)


class AtomFeedItem(BaseItem):
    unreadEntriesCounted = pyqtSignal(int)

    def __init__(self, feedid, title, icon=None,
                 offline=False, alwaysOffline=False):
        super(AtomFeedItem, self).__init__(title,
                                           icon=icon)

        self.feedId = feedid
        self.feedTitle = title
        self.unreadCount = 0
        self.setToolTip(self.feedId)

    def findEntryById(self, entryId):
        for item in self.childrenItems():
            if not isinstance(item, AtomFeedEntryItem):
                continue
            if item.entry.id == entryId:
                return item

    def updateTitle(self):
        unreadCount = 0
        for item in self.childrenItems():
            if not isinstance(item, AtomFeedEntryItem):
                # should not happen
                continue

            if item.entry.status == item.entry.ENTRY_STATUS_NEW:
                unreadCount += 1

        self.setText('{title} ({count})'.format(
            title=self.feedTitle,
            count=unreadCount
        ))

        if unreadCount != self.unreadCount:
            self.unreadCount = unreadCount
            self.parent().update()


class RootItemTracker(QObject):
    unreadCountChanged = pyqtSignal(int)


class RootItem(BaseItem):
    def __init__(self, text, icon=None):
        super(RootItem, self).__init__(text, icon=icon)

        self.unreadEntriesCount = 0
        self.tracker = RootItemTracker()

    def findFeedById(self, feedId):
        for item in self.childrenItems():
            if not isinstance(item, AtomFeedItem):
                continue
            if item.feedId == feedId:
                return item

    def update(self):
        self.unreadEntriesCount = self.unreadEntriesCalculate()
        self.tracker.unreadCountChanged.emit(self.unreadEntriesCount)

    def unreadEntriesCalculate(self):
        total = 0
        for item in self.childrenItems():
            if isinstance(item, AtomFeedItem):
                total += item.unreadCount
        return total


class AtomFeedsModel(QStandardItemModel):
    # An item's view was refreshed
    needExpand = pyqtSignal(QModelIndex)
    feedEntryAdded = pyqtSignal(AtomFeedEntryItem)

    def __init__(self, feedsDb, parent=None):
        super(AtomFeedsModel, self).__init__(parent)
        self.app = QApplication.instance()
        self.db = feedsDb

        self.db.processedFeedEntry.connect(self.onProcessedEntry)
        self.db.feedRemoved.connect(self.onFeedRemoved)

        self.itemRoot = RootItem('Root')

        self.invisibleRootItem().appendRow(self.itemRoot)
        self.itemRootIdx = self.indexFromItem(self.itemRoot)

        self.setHorizontalHeaderLabels(['Title', 'Date'])

    @property
    def root(self):
        return self.itemRoot

    def markEntryAsRead(self, entryItem):
        entryItem.entry.status = entryItem.entry.ENTRY_STATUS_READ
        if entryItem.entry.srow_id:
            ensure(self.db.feedEntrySetStatus(entryItem.entry.srow_id,
                                              entryItem.entry.status))

    def onFeedRemoved(self, feedId):
        child = self.itemRoot.findFeedById(feedId)
        if child:
            self.itemRoot.removeRow(child.row())

    def onProcessedEntry(self, feed, entry):
        child = self.itemRoot.findFeedById(feed.id)
        if not child:
            feedItem = AtomFeedItem(feed.id, feed.title)
            self.itemRoot.appendRow(feedItem)
        else:
            feedItem = child

        entryFound = feedItem.findEntryById(entry.id)
        if not entryFound:
            entryItem = AtomFeedEntryItem(entry)
            date = entry.published

            dateItem = BaseItem(
                date.strftime('%Y-%m-%d %H:%M') if date else iUnknown()
            )
            feedItem.appendRow([
                entryItem,
                dateItem
            ])

            self.feedEntryAdded.emit(entryItem)
