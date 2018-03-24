
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
from PyQt5.QtWidgets import QMessageBox, QMenu, QAbstractItemView

from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget

from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtGui import QPixmap, QIcon, QClipboard

from PyQt5.QtCore import QCoreApplication, QUrl, Qt, QEvent, QObject, pyqtSignal
from PyQt5.QtCore import QBuffer, QModelIndex, QMimeData, QFile, QStandardPaths
from PyQt5.Qt import QByteArray

from quamash import QEventLoop, QThreadExecutor

from galacteek.ipfs.ipfsops import *

from . import ui_files
from . import mediaplayer
from . import galacteek_rc
from . import modelhelpers
from .i18n import *
from .helpers import *

import aioipfs

# Files messages
def iFileName():
    return QCoreApplication.translate('FilesForm', 'Name')

def iFileSize():
    return QCoreApplication.translate('FilesForm', 'Size')
def iFileHash():
    return QCoreApplication.translate('FilesForm', 'Hash')

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

def iSelectDirectory():
    return QCoreApplication.translate('FilesForm', 'Select directory')

def iSelectFiles():
    return QCoreApplication.translate('FilesForm',
        'Select one or more files to import')

def iMyFiles():
    return QCoreApplication.translate('FilesForm', 'My Files')

class IPFSItem(QStandardItem):
    def __init__(self, text, icon=None):
        if icon:
            super().__init__(icon, text)
        else:
            super().__init__(text)
        self.setEditable(False)

        self.setParentHash(None)

    def setParentHash(self, hash):
        self.parentHash = hash

class treeKeyFilter(QObject):
    delKeyPressed = pyqtSignal()
    ctrlcPressed = pyqtSignal()
    ctrlvPressed = pyqtSignal()

    def eventFilter(self,  obj,  event):
        if event.type() == QEvent.KeyPress:
            modifiers = event.modifiers()

            key = event.key()
            if modifiers & Qt.ControlModifier:
                if key == Qt.Key_C:
                    self.ctrlcPressed.emit()
                if key == Qt.Key_V:
                    self.ctrlvPressed.emit()

            if event.key() == Qt.Key_Delete:
                self.delKeyPressed.emit()
                return True
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

class FilesTab(QWidget):
    def __init__(self, mainWindow, parent = None):
        super(QWidget, self).__init__(parent = parent)

        self.mainWindow = mainWindow
        self.app = mainWindow.getApp()
        self.lock = asyncio.Lock()

        self.ui = ui_files.Ui_FilesForm()
        self.ui.setupUi(self)
        self.clipboard = self.mainWindow.getApp().clipboard()

        # Connect the various buttons
        self.ui.addFileButton.clicked.connect(self.onAddFilesClicked)
        self.ui.addDirectoryButton.clicked.connect(self.onAddDirClicked)
        self.ui.refreshButton.clicked.connect(self.onRefreshClicked)
        self.ui.searchFiles.returnPressed.connect(self.onSearchFiles)

        # Connect the tree view actions
        self.ui.treeFiles.doubleClicked.connect(self.onDoubleClicked)
        self.ui.treeFiles.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.treeFiles.customContextMenuRequested.connect(self.onContextMenu)

        # Connect the event filter
        evfilter = treeKeyFilter(self.ui.treeFiles)
        evfilter.ctrlcPressed.connect(self.onCtrlC)
        evfilter.ctrlvPressed.connect(self.onCtrlV)
        self.ui.treeFiles.installEventFilter(evfilter)

        # Setup the model
        self.model = IPFSItemModel(self)
        self.model.setColumnCount(3)

        # Setup the tree view
        self.ui.treeFiles.setModel(self.model)
        self.ui.treeFiles.setAnimated(True)
        self.ui.treeFiles.setColumnWidth(0, 400)
        self.ui.treeFiles.setExpandsOnDoubleClick(False)
        self.ui.treeFiles.setSortingEnabled(True)
        self.ui.treeFiles.sortByColumn(0, Qt.AscendingOrder)

        self.iconFolder = getIcon('folder-open.png')
        self.iconFile = getIcon('file.png')

        # Configure drag-and-drop
        self.ui.treeFiles.setAcceptDrops(True)
        self.ui.treeFiles.setDragDropMode(QAbstractItemView.DropOnly)

        self.prepareTree()

    def enableButtons(self, flag=True):
        for btn in [ self.ui.addFileButton,
                self.ui.addDirectoryButton,
                self.ui.refreshButton,
                self.ui.searchFiles ]:
            btn.setEnabled(flag)

    def onCtrlC(self):
        currentIdx = self.ui.treeFiles.currentIndex()
        idxHash = self.model.index(currentIdx.row(), 2, currentIdx.parent())
        dataHash = self.model.data(idxHash)
        self.clipboard.setText(dataHash, QClipboard.Selection)

    def onCtrlV(self):
        pass

    def onContextMenu(self, point):
        idx = self.ui.treeFiles.indexAt(point)
        if not idx.isValid() or idx == self.itemFilesIdx:
            return

        idxHash = self.model.index(idx.row(), 2, idx.parent())
        idxPath = self.model.index(idx.row(), 0, idx.parent())
        dataHash = self.model.data(idxHash)
        dataPath = self.model.data(idxPath)
        menu = QMenu()

        def remove(hash):
            self.scheduleRemove(hash)

        def copyHashToClipboard(itemHash, clipboardType):
            self.clipboard.setText(itemHash, clipboardType)

        act1 = menu.addAction(iCopyHashToSelClipboard(), lambda:
                copyHashToClipboard(dataHash, QClipboard.Selection))
        act2 = menu.addAction(iCopyHashToGlobalClipboard(), lambda:
                copyHashToClipboard(dataHash, QClipboard.Clipboard))
        act2 = menu.addAction(iRemoveFile(), lambda:
                remove(dataHash))
        menu.exec(self.ui.treeFiles.mapToGlobal(point))

    def onDoubleClicked(self, idx):
        item = self.model.itemFromIndex(idx)
        data = item.data()
        idxHash = self.model.index(idx.row(), 2, idx.parent())
        itemHash = self.model.data(idxHash)
        if itemHash:
            self.mainWindow.addBrowserTab().browseIpfsHash(itemHash)

    def onSearchFiles(self):
        search = self.ui.searchFiles.text()
        self.ui.searchFiles.clear()
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

        def success():
            self.updateTree()
            msgBox = QMessageBox()
            msgBox.setText("The file was successfully added")
            msgBox.exec()

        self.scheduleAddFiles(result[0])

    def scheduleAddFiles(self, path):
        self.app.ipfsTaskOp(self.addFiles, path)

    def scheduleAddDirectory(self, path):
        self.app.ipfsTaskOp(self.addDirectory, path)

    def scheduleRemove(self, hash):
        self.app.ipfsTaskOp(self.removeFileFromHash, hash)

    def prepareTree(self):
        self.model.setHorizontalHeaderLabels(
                [iFileName(), iFileSize(), iFileHash()])
        self.itemRoot = self.model.invisibleRootItem()
        self.itemFiles = IPFSItem(iMyFiles())
        self.itemRoot.appendRow(self.itemFiles)

        self.itemRootIdx = self.model.indexFromItem(self.itemRoot)
        self.itemFilesIdx = self.model.indexFromItem(self.itemFiles)
        self.ui.treeFiles.expand(self.itemFilesIdx)

    def updateTree(self, highlight=None):
        async def listFiles(op, path, parentItem):
            self.enableButtons(flag=False)
            try:
                await op.client.files.flush(GFILES_MYFILES_PATH)
                await asyncio.wait_for(
                        listPath(op, path, parentItem=parentItem),
                        120)
            except aioipfs.APIException:
                messageBox(iErrNoCx())

            self.enableButtons()

        async def listPath(op, path, parentItem=None):
            self.statusLoading(path)

            listing = await op.filesList(path)
            if not listing:
                return

            parentItemSibling = self.model.sibling(parentItem.row(), 2,
                    parentItem.index())
            parentItemHash = self.model.data(parentItemSibling)

            for entry in listing:
                await asyncio.sleep(0)
                found = modelhelpers.modelSearch(self.model,
                        parent=self.itemRootIdx,
                        search=entry['Hash'], columns=[2])

                if len(found) > 0:
                    idx = found[0]
                    data = self.model.data(idx)
                    if highlight and highlight == data:
                        self.ui.treeFiles.expand(idx)
                    continue

                if entry['Type'] == 1: # directory
                    icon = self.iconFolder
                else:
                    icon = self.iconFile

                nItemName = IPFSItem(entry['Name'], icon)
                nItemSize = IPFSItem(str(entry['Size']))
                nItemHash = IPFSItem(entry['Hash'])
                nItemName.setParentHash(parentItemHash)
                nItem = [nItemName, nItemSize, nItemHash]

                if parentItem:
                    parentItem.appendRow(nItem)
                else:
                    self.itemFiles.appendRow(nItem)

                if entry['Type'] == 1: # directory
                    await asyncio.sleep(0)
                    await listPath(op,
                        os.path.join(path, entry['Name']),
                        parentItem=nItemName)

            self.ui.treeFiles.expand(self.itemFilesIdx)

        self.app.ipfsTaskOp(listFiles, GFILES_MYFILES_PATH,
                parentItem=self.itemFiles)

    async def removeFileFromHash(self, op, hash):
        listing = await op.filesList(GFILES_MYFILES_PATH)
        for entry in listing:
            if entry['Hash'] == hash:
                await op.filesDelete(GFILES_MYFILES_PATH,
                    entry['Name'], recursive=True)
                modelhelpers.modelDelete(self.model, hash)

    async def addFiles(self, op, files):
        """ Add every file with a wrapper directory by default to preserve
            filenames and use the wrapper directory's hash as a link
            Will soon turn this into a configurable option in the GUI """

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

            base = os.path.basename(file)
            await self.linkEntry(op, root, GFILES_MYFILES_PATH, base)
            last = root['Hash']

        self.updateTree()
        return True

    async def addDirectory(self, op, path):
        basename = os.path.basename(path)
        dirEntry = None

        async for added in op.client.add(path, recursive=True,
                wrap_with_directory=True):
            entryName = added['Name']
            self.statusAdded(entryName)
            if entryName == basename:
                dirEntry = added

        if not dirEntry:
            # Nothing went through ?
            return

        await self.linkEntry(op, dirEntry, GFILES_MYFILES_PATH, basename)

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
                await op.filesLink(entry, GFILES_MYFILES_PATH, name=lNew)
                break
