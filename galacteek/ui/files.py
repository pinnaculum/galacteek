
import sys
import time
import os.path
import asyncio
import cid

from PyQt5.QtWidgets import (QWidget, QFrame, QApplication, QMainWindow,
        QDialog, QLabel, QTextEdit, QPushButton, QVBoxLayout, QAction,
        QTabWidget, QFileDialog)
from PyQt5.QtWidgets import (QTreeWidget, QTreeWidgetItem)
from PyQt5.QtWidgets import (QTreeView, QTreeWidgetItem)
from PyQt5.QtWidgets import QMessageBox, QMenu, QAbstractItemView, QShortcut

from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtGui import QPixmap, QIcon, QClipboard, QKeySequence

from PyQt5.QtCore import QCoreApplication, QUrl, Qt, QEvent, QObject, pyqtSignal
from PyQt5.QtCore import QBuffer, QModelIndex, QMimeData, QFile, QStandardPaths
from PyQt5.Qt import QByteArray

from quamash import QEventLoop, QThreadExecutor

from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.cache import IPFSEntryCache

from . import ui_files
from . import mediaplayer
from . import galacteek_rc
from . import modelhelpers
from .i18n import *
from .helpers import *
from .widgets import GalacteekTab
from .bookmarks import *

import aioipfs

# Files messages
def iFileImportError():
    return QCoreApplication.translate('FilesForm', 'Error importing file {}')

def iCopyHashToSelClipboard():
    return QCoreApplication.translate('FilesForm',
        "Copy file's hash to selection clipboard")

def iCopyHashToGlobalClipboard():
    return QCoreApplication.translate('FilesForm',
        "Copy file's hash to global clipboard")

def iAddedFile(name):
    return QCoreApplication.translate('FilesForm',
            'Added file {0}').format(name)
def iLoadingFile(name):
    return QCoreApplication.translate('FilesForm',
            'Loading file {0}').format(name)
def iLoading(name):
    return QCoreApplication.translate('FilesForm',
            'Loading {0}').format(name)

def iRemoveFile():
    return QCoreApplication.translate('FilesForm', 'Remove file')

def iUnlinkFile():
    return QCoreApplication.translate('FilesForm', 'Unlink file')

def iBookmarkFile():
    return QCoreApplication.translate('FilesForm', 'Bookmark')

def iBrowseFile():
    return QCoreApplication.translate('FilesForm', 'Browse')

def iSelectDirectory():
    return QCoreApplication.translate('FilesForm', 'Select directory')

def iSelectFiles():
    return QCoreApplication.translate('FilesForm',
        'Select one or more files to import')

def iMyFiles():
    return QCoreApplication.translate('FilesForm', 'My Files')

class IPFSItem(UneditableItem):
    def __init__(self, text, icon=None):
        super().__init__(text, icon=icon)
        self.path = None
        self.setParentHash(None)

    def setParentHash(self, hash):
        self.parentHash = hash

    def getParentHash(self):
        return self.parentHash

    def setPath(self, path):
        self.path = path

    def getPath(self):
        return self.path

class IPFSNameItem(IPFSItem):
    def __init__(self, entry, text, icon):
        super().__init__(text, icon=icon)
        self.entry = entry

    def getEntry(self):
        return self.entry

    def isFile(self):
        return self.entry['Type'] == 0

    def isDir(self):
        return self.entry['Type'] == 1

class treeKeyFilter(QObject):
    deletePressed = pyqtSignal()
    copyPressed = pyqtSignal()
    returnPressed = pyqtSignal()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            modifiers = event.modifiers()

            key = event.key()
            if key == Qt.Key_Return:
                self.returnPressed.emit()
            if modifiers & Qt.ControlModifier:
                if key == Qt.Key_C:
                    self.copyPressed.emit()

            if event.key() == Qt.Key_Delete:
                self.deletePressed.emit()
            return False
        return False

class IPFSItemModel(QStandardItemModel):
    def __init__(self, parent, *args, **kw):
        QStandardItemModel.__init__(self, *args, **kw)

        self.filesW = parent

    def supportedDropActions(self):
        return Qt.CopyAction | Qt.MoveAction | Qt.TargetMoveAction | Qt.LinkAction

    def flagsUnused(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | \
               Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled

    def mimeData(self, indexes):
        mimedata = QMimeData()
        return mimedata

    def dropMimeData(self, data, action, row, column, parent):
        mimeText = data.text()
        try:
            path = QUrl(mimeText).toLocalFile()
            if os.path.isfile(path):
                self.filesW.scheduleAddFiles([path])
            if os.path.isdir(path):
                self.filesW.scheduleAddDirectory(path)
        except Exception as e:
            print('Drag and drop error', str(e), file=sys.stderr)

        return True

    def canDropMimeData(self, data, action, row, column, parent):
        mimeText = data.text()

        if mimeText and mimeText.startswith('file://'):
            return True
        return False

    def getHashFromIdx(self, idx):
        idxHash = self.index(idx.row(), 2, idx.parent())
        return self.data(idxHash)

    def getNameFromIdx(self, idx):
        idxName = self.index(idx.row(), 0, idx.parent())
        return self.data(idxName)

    def getNameItemFromIdx(self, idx):
        idxName = self.index(idx.row(), 0, idx.parent())
        return self.itemFromIndex(idxName)

class FilesTab(GalacteekTab):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

        self.lock = asyncio.Lock()

        self.ui = ui_files.Ui_FilesForm()
        self.ui.setupUi(self)
        self.clipboard = self.gWindow.getApp().clipboard()

        # Connect the various buttons
        self.ui.addFileButton.clicked.connect(self.onAddFilesClicked)
        self.ui.addDirectoryButton.clicked.connect(self.onAddDirClicked)
        self.ui.refreshButton.clicked.connect(self.onRefreshClicked)
        self.ui.searchFiles.returnPressed.connect(self.onSearchFiles)

        # Connect the tree view actions
        self.ui.treeFiles.doubleClicked.connect(self.onDoubleClicked)
        self.ui.treeFiles.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.treeFiles.customContextMenuRequested.connect(self.onContextMenu)
        self.ui.treeFiles.expanded.connect(self.onExpanded)

        # Connect the event filter
        evfilter = treeKeyFilter(self.ui.treeFiles)
        evfilter.copyPressed.connect(self.onCopyItemHash)
        evfilter.returnPressed.connect(self.onReturn)
        self.ui.treeFiles.installEventFilter(evfilter)

        # Setup the model
        self.model = IPFSItemModel(self)
        self.model.setColumnCount(3)
        self.entryCache = IPFSEntryCache()

        # Setup the tree view
        self.ui.treeFiles.setModel(self.model)
        self.ui.treeFiles.setColumnWidth(0, 400)
        self.ui.treeFiles.setExpandsOnDoubleClick(True)
        self.ui.treeFiles.setItemsExpandable(True)
        self.ui.treeFiles.setSortingEnabled(True)
        self.ui.treeFiles.sortByColumn(0, Qt.AscendingOrder)

        self.iconFolder = getIcon('folder-open.png')
        self.iconFile = getIcon('file.png')

        # Configure drag-and-drop
        self.ui.treeFiles.setAcceptDrops(True)
        self.ui.treeFiles.setDragDropMode(QAbstractItemView.DropOnly)

        self.ipfsKeys = []

        self.prepareTree()

    def enableButtons(self, flag=True):
        for btn in [ self.ui.addFileButton,
                self.ui.addDirectoryButton,
                self.ui.refreshButton,
                self.ui.searchFiles ]:
            btn.setEnabled(flag)

    def onCopyItemHash(self):
        currentIdx = self.ui.treeFiles.currentIndex()
        dataHash = self.model.getHashFromIdx(currentIdx)
        self.clipboard.setText(dataHash, QClipboard.Selection)

    def onReturn(self):
        currentIdx = self.ui.treeFiles.currentIndex()
        dataHash = self.model.getHashFromIdx(currentIdx)
        if dataHash:
            self.gWindow.addBrowserTab().browseIpfsHash(dataHash)

    def onExpanded(self, idx):
        dataHash = self.model.getHashFromIdx(idx)
        dataName = self.model.getNameFromIdx(idx)

        it = self.model.itemFromIndex(idx)

    def onContextMenu(self, point):
        idx = self.ui.treeFiles.indexAt(point)
        if not idx.isValid() or idx == self.itemFilesIdx:
            return

        nameItem = self.model.getNameItemFromIdx(idx)
        dataHash = self.model.getHashFromIdx(idx)
        dataPath = self.model.getNameFromIdx(idx)
        ipfsPath = joinIpfs(dataHash)
        menu = QMenu()

        def unlink(hash):
            self.scheduleUnlink(hash)

        def bookmark(mPath, name):
            addBookmark(self.app.marksLocal, mPath, name)

        def browse(hash):
            self.browse(hash)

        def copyHashToClipboard(itemHash, clipboardType):
            self.clipboard.setText(itemHash, clipboardType)

        menu.addAction(iCopyHashToSelClipboard(), lambda:
            copyHashToClipboard(dataHash, QClipboard.Selection))
        menu.addAction(iCopyHashToGlobalClipboard(), lambda:
            copyHashToClipboard(dataHash, QClipboard.Clipboard))
        menu.addAction(iUnlinkFile(), lambda:
            unlink(dataHash))
        menu.addAction(iBookmarkFile(), lambda:
            bookmark(ipfsPath, nameItem.getEntry()['Name']))
        menu.addAction(iBrowseFile(), lambda:
            browse(dataHash))

        def publishToKey(action):
            key = action.data()['key']['Name']
            oHash = action.data()['hash']

            async def publish(op, oHash, keyName):
                r = await op.publish(joinIpfs(oHash), key=keyName)

            self.app.ipfsTaskOp(publish, oHash, key)

        # Populate publish menu
        publishMenu = QMenu('Publish to IPFS key')
        for key in self.ipfsKeys:
            action = QAction(key['Name'], self)
            action.setData({
                'key': key,
                'hash': dataHash
            })

            publishMenu.addAction(action)

        publishMenu.triggered.connect(publishToKey)

        menu.addMenu(publishMenu)
        menu.exec(self.ui.treeFiles.mapToGlobal(point))

    def browse(self, hash):
        self.gWindow.addBrowserTab().browseIpfsHash(hash)

    def browseFs(self, path):
        self.gWindow.addBrowserTab().browseFsPath(path)

    def onDoubleClicked(self, idx):
        if not idx.isValid() or idx == self.itemFilesIdx:
            return

        nameItem = self.model.getNameItemFromIdx(idx)
        item = self.model.itemFromIndex(idx)
        dataHash = self.model.getHashFromIdx(idx)
        dataPath = self.model.getNameFromIdx(idx)

        if nameItem.isFile():
            # Find the parent hash
            parentHash = nameItem.getParentHash()
            if parentHash:
                # We have the parent hash, so use it to build a file path
                # preserving the real file name
                path = joinIpfs(os.path.join(parentHash,
                    nameItem.text()))
                return self.browseFs(path)
            else:
                return self.browse(dataHash)

        self.app.ipfsTaskOp(self.listFiles, item.getPath(), parentItem=item,
            autoexpand=True)

    def onSearchFiles(self):
        search = self.ui.searchFiles.text()
        self.ui.treeFiles.keyboardSearch(search)

    def onRefreshClicked(self):
        self.updateTree()

    def onAddDirClicked(self):
        result = QFileDialog.getExistingDirectory(None,
            iSelectDirectory(), getHomePath(),
            QFileDialog.ShowDirsOnly)
        if result:
            self.scheduleAddDirectory(result)

    def statusAdded(self, name):
        self.statusSet(iAddedFile(name))

    def statusLoading(self, name):
        self.statusSet(iLoading(name))

    def statusSet(self, msg):
        self.ui.statusLabel.setText(msg)

    def onAddFilesClicked(self):
        result = QFileDialog.getOpenFileNames(None,
            iSelectFiles(), getHomePath(), '(*.*)')
        if not result:
            return

        self.scheduleAddFiles(result[0])

    def scheduleAddFiles(self, path):
        return self.app.ipfsTaskOp(self.addFiles, path)

    def scheduleAddDirectory(self, path):
        return self.app.ipfsTaskOp(self.addDirectory, path)

    def scheduleUnlink(self, hash):
        return self.app.ipfsTaskOp(self.unlinkFileFromHash, hash)

    def prepareTree(self):
        self.model.setHorizontalHeaderLabels(
                [iFileName(), iFileSize(), iFileHash()])
        self.itemRoot = self.model.invisibleRootItem()
        self.itemFiles = IPFSItem(iMyFiles())
        self.itemFiles.setPath(GFILES_MYFILES_PATH)
        self.itemRoot.appendRow(self.itemFiles)

        self.itemRootIdx = self.model.indexFromItem(self.itemRoot)
        self.itemFilesIdx = self.model.indexFromItem(self.itemFiles)
        self.ui.treeFiles.expand(self.itemFilesIdx)

    def updateTree(self):
        async def _updateKeys(op):
            self.ipfsKeys = await op.keys()

        self.app.ipfsTaskOp(_updateKeys)
        self.app.ipfsTaskOp(self.listFiles, GFILES_MYFILES_PATH,
            parentItem=self.itemFiles, maxdepth=1)

    async def listFiles(self, op, path, parentItem, maxdepth=0,
            autoexpand=False):
        self.enableButtons(flag=False)
        try:
            await op.client.files.flush(GFILES_MYFILES_PATH)
            await asyncio.wait_for(
                    self.listPath(op, path, parentItem=parentItem,
                        maxdepth=maxdepth, autoexpand=autoexpand), 120)
        except aioipfs.APIException:
            messageBox(iErrNoCx())

        self.enableButtons()

    async def listPath(self, op, path, parentItem=None, depth=0, maxdepth=1,
            autoexpand=False):
        self.statusLoading(path)

        if not parentItem.getPath():
            return

        listing = await op.filesList(path)
        if not listing:
            return

        parentItemSibling = self.model.sibling(parentItem.row(), 2,
                parentItem.index())
        parentItemHash = self.model.data(parentItemSibling)

        for entry in listing:
            await asyncio.sleep(0)
            if entry['Hash'] == '':
                continue

            if entry['Hash'] in self.entryCache:
                continue

            if entry['Type'] == 1: # directory
                icon = self.iconFolder
            else:
                icon = self.iconFile

            nItemName = IPFSNameItem(entry, entry['Name'], icon)
            nItemName.setParentHash(parentItemHash)
            nItemSize = IPFSItem(str(entry['Size']))
            nItemHash = IPFSItem(entry['Hash'])

            nItemName.setPath(os.path.join(parentItem.getPath(),
                entry['Name']))

            nItem = [nItemName, nItemSize, nItemHash]

            parentItem.appendRow(nItem)

            self.entryCache.register(entry)

            if entry['Type'] == 1: # directory
                if autoexpand is True:
                    self.ui.treeFiles.setExpanded(nItemName.index(), True)
                await asyncio.sleep(0)
                if maxdepth > depth:
                    depth += 1
                    await self.listPath(op,
                        nItemName.getPath(),
                        parentItem=nItemName,
                        maxdepth=maxdepth, depth=depth)
                    depth -= 1

        if autoexpand is True:
            self.ui.treeFiles.expand(parentItem.index())

    async def unlinkFileFromHash(self, op, hash):
        listing = await op.filesList(GFILES_MYFILES_PATH)
        for entry in listing:
            if entry['Hash'] == hash:
                await op.filesDelete(GFILES_MYFILES_PATH,
                    entry['Name'], recursive=True)
                await modelhelpers.modelDeleteAsync(self.model, hash)

    async def addFiles(self, op, files):
        """ Add every file with a wrapper directory by default to preserve
            filenames and use the wrapper directory's hash as a link
            Will soon turn this into a configurable option in the GUI """

        self.enableButtons(flag=False)
        last = None
        for file in files:
            root = None
            async for added in op.client.add(file, wrap_with_directory=True):
                await asyncio.sleep(0)
                fileName = added['Name']
                if fileName == '': # keep track of the directory wrapper
                    root = added
                    continue

                self.statusAdded(fileName)

            if root is None:
                self.statusSet(iFileImportError())
                continue

            base = os.path.basename(file) + '.dirw'
            await self.linkEntry(op, root, GFILES_MYFILES_PATH, base)
            last = root['Hash']

        self.enableButtons()
        self.updateTree()
        return True

    async def addDirectory(self, op, path):
        self.enableButtons(flag=False)
        basename = os.path.basename(path)
        dirEntry = None

        async for added in op.client.add(path, recursive=True,
                wrap_with_directory=True, hidden=False):
            await asyncio.sleep(0)
            entryName = added['Name']
            self.statusAdded(entryName)
            if entryName == basename:
                dirEntry = added

        if not dirEntry:
            # Nothing went through ?
            self.enableButtons()
            return

        await self.linkEntry(op, dirEntry, GFILES_MYFILES_PATH, basename)

        self.enableButtons()
        self.updateTree()
        return True

    async def linkEntry(self, op, entry, dest, basename):
        for lIndex in range(0, 16):
            await asyncio.sleep(0)
            if lIndex == 0:
                lNew = basename
            else:
                lNew = '{0}.{1}'.format(basename, lIndex)
            lookup = await op.filesLookup(GFILES_MYFILES_PATH, lNew)
            if not lookup:
                if await op.filesLink(entry, GFILES_MYFILES_PATH, name=lNew):
                    break
