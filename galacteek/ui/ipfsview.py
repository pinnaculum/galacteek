
import sys
import time
import os.path
import mimetypes

from PyQt5.QtWidgets import (QWidget, QFrame, QApplication,
        QLabel, QPushButton, QVBoxLayout, QAction, QHBoxLayout,
        QTreeView, QHeaderView, QShortcut, QToolBox, QTextBrowser)

from PyQt5.QtGui import QStandardItemModel, QStandardItem, QKeySequence

from PyQt5.QtCore import (QCoreApplication, QUrl, Qt, QEvent, QObject,
    pyqtSignal, QMimeData)

from galacteek.appsettings import *
from galacteek.ipfs import cidhelpers
from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.wrappers import ipfsOp, ipfsStatOp
from galacteek.ipfs.cache import IPFSEntryCache

from . import galacteek_rc
from . import modelhelpers
from .i18n import *
from .helpers import *
from .widgets import GalacteekTab
from .bookmarks import *

import aioipfs

def iCIDInfo(cidv, linksCount, size):
    return QCoreApplication.translate('IPFSHashView',
        'CID (v{0}): {1} links, total size: {2}').format(
            cidv, linksCount, size)

class IPFSItem(UneditableItem):
    def __init__(self, text, icon=None):
        super().__init__(text, icon=icon)
        self.setParentHash(None)

    def setParentHash(self, hash):
        self.parentHash = hash

    def getParentHash(self):
        return self.parentHash

class IPFSNameItem(IPFSItem):
    def __init__(self, entry, text, icon):
        super().__init__(text, icon=icon)

        self.entry = entry
        self.mimeType = mimetypes.guess_type(entry['Name'])[0]

    def getEntry(self):
        return self.entry

    @property
    def mimeCategory(self):
        if self.mimeType:
            return self.mimeType.split('/')[0]

    def cid(self):
        return cidhelpers.getCID(self.getEntry()['Hash'])

    def isRaw(self):
        return self.getEntry()['Type'] == 0

    def isDir(self):
        return self.getEntry()['Type'] == 1

    def isFile(self):
        return self.getEntry()['Type'] == 2

    def isMetadata(self):
        return self.getEntry()['Type'] == 3

    def isSymlink(self):
        return self.getEntry()['Type'] == 4

    def isUnknown(self):
        return self.getEntry()['Type'] == -1

class IPFSHashItemModel(QStandardItemModel):
    COL_NAME = 0
    COL_SIZE = 1
    COL_MIME = 2
    COL_HASH = 3

    def __init__(self, parent, *args, **kw):
        QStandardItemModel.__init__(self, *args, **kw)

        self.entryCache = IPFSEntryCache()
        self.rowsInserted.connect(self.onRowsInserted)

    def canDropMimeData(self, data, action, row, column, parent):
        return False

    def getHashFromIdx(self, idx):
        idxHash = self.index(idx.row(), self.COL_HASH, idx.parent())
        return self.data(idxHash)

    def getNameFromIdx(self, idx):
        idxName = self.index(idx.row(), self.COL_NAME, idx.parent())
        return self.data(idxName)

    def getNameItemFromIdx(self, idx):
        idxName = self.index(idx.row(), self.COL_NAME, idx.parent())
        return self.itemFromIndex(idxName)

    def onRowsInserted(self, parent, first, last):
        """ Update the entry cache when rows are added """
        for itNum in range(first, last+1):
            itNameIdx = self.index(itNum, self.COL_NAME, parent)
            itName = self.itemFromIndex(itNameIdx)
            entry = itName.getEntry()
            self.entryCache.register(entry)

class IPFSHashViewToolBox(GalacteekTab):
    """
    Organizes IPFSHashViewWidgets with a QToolBox
    """
    def __init__(self, gWindow, hashRef, maxItems=16, parent=None):
        super(IPFSHashViewToolBox, self).__init__(gWindow)

        self.rootHash = hashRef
        self.maxItems = maxItems

        self.toolbox = QToolBox()
        self.vLayout = QVBoxLayout(self)
        self.vLayout.addWidget(self.toolbox)

        if self.rootHash:
            self.viewHash(self.rootHash)

    @property
    def itemsCount(self):
        return self.toolbox.count()

    def viewHash(self, hashRef, addClose=False, autoOpenFolders=False):
        w = self.lookup(hashRef)
        if w:
            self.toolbox.setCurrentWidget(w)
            return True

        if self.itemsCount > self.maxItems:
            return False

        view = IPFSHashViewWidget(self.gWindow, hashRef,
                parent=self, addClose=addClose,
                autoOpenFolders=autoOpenFolders)
        idx = self.toolbox.addItem(view, getIconIpfsWhite(), hashRef)
        self.toolbox.setCurrentIndex(idx)
        view.reFocus()
        return True

    def lookup(self, hashRef):
        for idx in range(self.itemsCount):
            if self.toolbox.itemText(idx) == hashRef:
                return self.toolbox.widget(idx)

    def remove(self, view):
        idx = self.toolbox.indexOf(view)
        if idx:
            self.toolbox.removeItem(idx)
            # Always display previous index in the stack
            if self.itemsCount > 0:
                rIdx = idx - 1
                view = self.toolbox.widget(rIdx)
                if view:
                    self.toolbox.setCurrentWidget(view)
                    view.reFocus()

class TreeEventFilter(QObject):
    copyPressed = pyqtSignal()
    returnPressed = pyqtSignal()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            modifiers = event.modifiers()

            key = event.key()
            if key == Qt.Key_Return:
                self.returnPressed.emit()
                return True
            if modifiers & Qt.ControlModifier:
                if key == Qt.Key_C:
                    self.copyPressed.emit()
                    return True
        return False

class TextView(QWidget):
    def __init__(self, data, mimeType, parent=None):
        super(TextView, self).__init__(parent)

        self.textData = self.decode(data)

        if not self.textData:
            self.textData = 'Error decoding data'

        self.vLayout = QVBoxLayout(self)

        self.textBrowser = QTextBrowser()
        if mimeType == 'text/html':
            self.textBrowser.setHtml(self.textData)
        else:
            self.textBrowser.setPlainText(self.textData)

        self.vLayout.addWidget(self.textBrowser)
        self.setLayout(self.vLayout)

    def decode(self, data):
        for enc in ['utf-8', 'latin1', 'ascii']:
            try:
                textData = data.decode(enc)
            except:
                continue
            else:
                return textData

class HashTreeView(QTreeView):
    pass

class IPFSHashViewWidget(QWidget):
    def __init__(self, gWindow, hashRef, addClose=False,
            autoOpenFolders=False,
            parent=None):
        super(IPFSHashViewWidget, self).__init__(parent)

        self.parent = parent

        self.gWindow = gWindow
        self.app = gWindow.getApp()
        self.rootHash = hashRef
        self.rootPath = joinIpfs(self.rootHash)
        self.cid = cidhelpers.getCID(self.rootHash)

        self.vLayout = QVBoxLayout(self)

        self.autoOpenFolders = autoOpenFolders
        self.hLayoutTop = QHBoxLayout()
        self.labelInfo = QLabel()

        self.hLayoutTop.addWidget(self.labelInfo, 0, Qt.AlignLeft)

        if addClose:
            self.closeButton = QPushButton('Close')
            self.closeButton.clicked.connect(self.onClose)
            self.closeButton.setMaximumWidth(100)
            self.closeButton.setShortcut(QKeySequence('Ctrl+w'))
            self.hLayoutTop.addWidget(self.closeButton, 0, Qt.AlignLeft)

        self.vLayout.addLayout(self.hLayoutTop)

        self.tree = HashTreeView()
        self.vLayout.addWidget(self.tree)

        self.model = IPFSHashItemModel(self)
        self.model.setHorizontalHeaderLabels(
                [iFileName(), iFileSize(), iMimeType(), iFileHash()])
        self.itemRoot = self.model.invisibleRootItem()
        self.itemRootIdx = self.model.indexFromItem(self.itemRoot)

        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.onContextMenu)
        self.tree.doubleClicked.connect(self.onDoubleClicked)
        self.tree.setSortingEnabled(True)

        evfilter = IPFSTreeKeyFilter(self.tree)
        evfilter.copyHashPressed.connect(self.onCopyItemHash)
        evfilter.copyPathPressed.connect(self.onCopyItemPath)
        evfilter.returnPressed.connect(self.onReturnPressed)
        self.tree.installEventFilter(evfilter)
        self.iconFolder = getIcon('folder-open.png')
        self.iconFile = getIcon('file.png')

        self.updateTree()

    def setInfo(self, text):
        self.labelInfo.setText(text)

    def reFocus(self):
        self.tree.setFocus(Qt.OtherFocusReason)

    def onReturnPressed(self):
        currentIdx = self.tree.currentIndex()
        if currentIdx.isValid():
            self.onDoubleClicked(currentIdx)

    def onCopyItemHash(self):
        dataHash = self.model.getHashFromIdx(self.tree.currentIndex())
        self.app.setClipboardText(dataHash)

    def onCopyItemPath(self):
        dataHash = self.model.getHashFromIdx(self.tree.currentIndex())
        self.app.setClipboardText(joinIpfs(dataHash))

    def onClose(self):
        self.parent.remove(self)

    def browse(self, hash):
        self.gWindow.addBrowserTab().browseIpfsHash(hash)

    def onDoubleClicked(self, idx):
        nameItem = self.model.getNameItemFromIdx(idx)
        item = self.model.itemFromIndex(idx)
        dataHash = self.model.getHashFromIdx(idx)
        dataPath = self.model.getNameFromIdx(idx)

        if nameItem.isDir():
            self.parent.viewHash(dataHash, addClose=True)
        elif nameItem.isFile() or nameItem.isUnknown():
            self.openFile(nameItem, dataHash)

    def openFile(self, item, fileHash):
        if item.mimeType is None:
            return self.browse(fileHash)

        if item.mimeType == 'text/html':
            return self.browse(fileHash)

        self.gWindow.app.task(self.openFileWithMime, item, fileHash)

    @ipfsOp
    async def openFileWithMime(self, ipfsop, item, fileHash):
        if item.mimeCategory == 'text':
            data = await ipfsop.client.cat(fileHash)
            tView = TextView(data, item.mimeType, parent=self.gWindow)
            self.gWindow.registerTab(tView, item.getEntry()['Name'], current=True)
        elif item.mimeCategory == 'video' or item.mimeCategory == 'audio':
            return self.gWindow.addMediaPlayerTab(joinIpfs(fileHash))
        elif item.mimeCategory == 'image':
            return self.browse(fileHash)
        else:
            # Default
            return self.browse(fileHash)

    def updateTree(self):
        self.app.task(self.listHash, self.rootPath,
            parentItem=self.itemRoot)

    def onContextMenu(self, point):
        idx = self.tree.indexAt(point)
        if not idx.isValid():
            return

        menu = QMenu()
        nameItem = self.model.getNameItemFromIdx(idx)
        dataHash = self.model.getHashFromIdx(idx)
        dataPath = self.model.getNameFromIdx(idx)
        ipfsPath = joinIpfs(dataHash)

        def pinRecursive(rHash):
            self.app.task(self.app.pinner.enqueue, ipfsPath, True, None)

        menu.addAction(getIcon('pin-black.png'), 'Pin (recursive)',
                lambda: pinRecursive(dataHash))

        menu.exec(self.tree.mapToGlobal(point))

    @ipfsStatOp
    async def listHash(self, ipfsop, rHash, rStat, parentItem,
            autoexpand=False):
        """ Lists contents of IPFS object references by rHash,
            and change the tree's model afterwards """
        try:
            await self.list(ipfsop, rHash, parentItem=parentItem,
                    autoexpand=autoexpand)
            self.tree.setModel(self.model)
            self.tree.header().setSectionResizeMode(self.model.COL_NAME,
                    QHeaderView.ResizeToContents)
            self.tree.header().setSectionResizeMode(self.model.COL_MIME,
                    QHeaderView.ResizeToContents)
            self.tree.sortByColumn(self.model.COL_NAME, Qt.AscendingOrder)

            if self.app.settingsMgr.hideHashes:
                self.tree.hideColumn(self.model.COL_HASH)

            if rStat:
                self.setInfo(iCIDInfo(self.cid.version,
                    rStat['NumLinks'],
                    sizeFormat(rStat['CumulativeSize'])))
        except aioipfs.APIException:
            messageBox(iErrNoCx())

    async def list(self, op, path, parentItem=None,
            autoexpand=False):

        parentItemSibling = self.model.sibling(parentItem.row(),
                self.model.COL_HASH,
                parentItem.index())
        parentItemHash = self.model.data(parentItemSibling)
        if parentItemHash is None:
            parentItemHash = self.rootHash

        async for obj in op.list(path):
            for entry in obj['Links']:
                await op.sleep()

                if entry['Hash'] in self.model.entryCache:
                    continue

                if entry['Type'] == 1: # directory
                    icon = self.iconFolder
                else:
                    icon = self.iconFile

                nItemName = IPFSNameItem(entry, entry['Name'], icon)
                nItemName.setParentHash(parentItemHash)
                nItemSize = IPFSItem(sizeFormat(entry['Size']))
                nItemSize.setToolTip(str(entry['Size']))
                nItemMime = IPFSItem(nItemName.mimeType or iUnknown())
                nItemHash = IPFSItem(entry['Hash'])
                nItemName.setToolTip(entry['Hash'])

                nItem = [nItemName, nItemSize, nItemMime, nItemHash]
                parentItem.appendRow(nItem)

                if nItemName.isDir() and self.autoOpenFolders:
                    # Automatically open sub folders. Used by unit tests
                    self.parent.viewHash(entry['Hash'],
                        addClose=True, autoOpenFolders=self.autoOpenFolders)