import os.path
import asyncio
import functools

from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QTreeView
from PyQt5.QtWidgets import QMenu
from PyQt5.QtWidgets import QAbstractItemView
from PyQt5.QtWidgets import QInputDialog
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QFileSystemModel
from PyQt5.QtWidgets import QHeaderView

from PyQt5.QtGui import QStandardItemModel

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import QUrl
from PyQt5.QtCore import Qt
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QMimeData
from PyQt5.QtCore import QDir
from PyQt5.QtCore import QFile

from galacteek import ensure
from galacteek.ipfs.cidhelpers import joinIpfs
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.wrappers import ipfsOp
from galacteek.appsettings import *

from . import ui_files
from . import modelhelpers
from .i18n import *  # noqa
from .helpers import *  # noqa
from .widgets import GalacteekTab
from .hashmarks import *  # noqa
from .clipboard import iCopyMultihashToClipboard
from .clipboard import iCopyPathToClipboard

import aioipfs

# Files messages


def iFileImportError():
    return QCoreApplication.translate(
        'FileManagerForm', 'Error importing file {}')


def iAddedFile(name):
    return QCoreApplication.translate('FileManagerForm',
                                      'Added {0}').format(name)


def iImportedCount(count):
    return QCoreApplication.translate('FileManagerForm',
                                      'Imported {0} files').format(count)


def iLoadingFile(name):
    return QCoreApplication.translate('FileManagerForm',
                                      'Loading file {0}').format(name)


def iLoading(name):
    return QCoreApplication.translate('FileManagerForm',
                                      'Loading {0}').format(name)


def iOpenWith():
    return QCoreApplication.translate('FileManagerForm', 'Open with')


def iDeleteFile():
    return QCoreApplication.translate('FileManagerForm', 'Delete file')


def iExploreDir():
    return QCoreApplication.translate('FileManagerForm', 'Explore directory')


def iUnlinkFile():
    return QCoreApplication.translate('FileManagerForm', 'Unlink file')


def iHashmarkFile():
    return QCoreApplication.translate('FileManagerForm', 'Hashmark')


def iBrowseFile():
    return QCoreApplication.translate('FileManagerForm', 'Browse')


def iSelectDirectory():
    return QCoreApplication.translate('FileManagerForm', 'Select directory')


def iSelectFiles():
    return QCoreApplication.translate('FileManagerForm',
                                      'Select one or more files to import')


def iMusic():
    return QCoreApplication.translate('FileManagerForm', 'Music')


def iPictures():
    return QCoreApplication.translate('FileManagerForm', 'Pictures')


def iVideos():
    return QCoreApplication.translate('FileManagerForm', 'Videos')


def iHome():
    return QCoreApplication.translate('FileManagerForm', 'Home')


def iCode():
    return QCoreApplication.translate('FileManagerForm', 'Code')


def iDocuments():
    return QCoreApplication.translate('FileManagerForm', 'Documents')


def iWebPages():
    return QCoreApplication.translate('FileManagerForm', 'Web Pages')


def iQrCodes():
    return QCoreApplication.translate('FileManagerForm', 'QR codes')


class IPFSItem(UneditableItem):
    def __init__(self, text, path=None, parenthash=None, icon=None):
        super(IPFSItem, self).__init__(text, icon=icon)
        self._path = path
        self._parentHash = parenthash

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, v):
        self._path = v

    @property
    def parentHash(self):
        return self._parentHash

    def setParentHash(self, pHash):
        self._parentHash = pHash

    def childrenItems(self):
        for row in range(0, self.rowCount()):
            child = self.child(row, 0)
            if child:
                yield child

    def findChildByMultihash(self, multihash):
        for item in self.childrenItems():
            if not isinstance(item, IPFSNameItem):
                continue
            if item.entry['Hash'] == multihash:
                return item

    def findChildByName(self, name):
        for item in self.childrenItems():
            if not isinstance(item, IPFSNameItem):
                continue
            if item.entry['Name'] == name:
                return item


class IPFSNameItem(IPFSItem):
    def __init__(self, entry, text, icon):
        super().__init__(text, icon=icon)

        self._entry = entry
        self._mimeType = None

    @property
    def entry(self):
        return self._entry

    @property
    def ipfsPath(self):
        return IPFSPath(self.fullPath)

    @property
    def dwebUrl(self):
        return QUrl('dweb:{}'.format(self.fullPath))

    @property
    def mimeType(self):
        return self._mimeType

    def mimeFromDb(self, db):
        self._mimeType = db.mimeTypeForFile(self.entry['Name'])

    @property
    def mimeCategory(self):
        if self.mimeType:
            return self.mimeTypeName.split('/')[0]

    @property
    def mimeTypeName(self):
        if self.mimeType:
            return self.mimeType.name()

    @property
    def fullPath(self):
        parentHash = self.parentHash
        if parentHash:
            return joinIpfs(os.path.join(parentHash, self.entry['Name']))
        else:
            return joinIpfs(self.entry['Hash'])

    def isFile(self):
        return self.entry['Type'] == 0

    def isDir(self):
        return self.entry['Type'] == 1


class FilesItemModel(QStandardItemModel):
    fileDropEvent = pyqtSignal(str)
    directoryDropEvent = pyqtSignal(str)

    def __init__(self):
        QStandardItemModel.__init__(self)
        self.app = QApplication.instance()

        self.itemRoot = self.invisibleRootItem()
        self.itemRootIdx = self.indexFromItem(self.itemRoot)

    def setupItemsFromProfile(self, profile, model, filesM):
        self.itemHome = IPFSItem(iHome(), path=profile.pathHome)
        self.itemPictures = IPFSItem(iPictures(),
                                     path=profile.pathPictures)
        self.itemVideos = IPFSItem(iVideos(),
                                   path=profile.pathVideos)
        self.itemMusic = IPFSItem(iMusic(),
                                  path=profile.pathMusic)
        self.itemCode = IPFSItem(iCode(),
                                 path=profile.pathCode)
        self.itemDocuments = IPFSItem(iDocuments(),
                                      path=profile.pathDocuments)
        self.itemWebPages = IPFSItem(iWebPages(),
                                     path=profile.pathWebPages)
        self.itemQrCodes = IPFSItem(iQrCodes(),
                                    path=profile.pathQrCodes)

        self.itemRoot.appendRows([
            self.itemHome,
            self.itemPictures,
            self.itemVideos,
            self.itemCode,
            self.itemMusic,
            self.itemDocuments,
            self.itemWebPages,
            self.itemQrCodes
        ])

        ensure(self.setupQrCodesFolder(profile, model, filesM))

    @ipfsOp
    async def setupQrCodesFolder(self, ipfsop, profile, model, files):
        """
        Import the sample QR codes to the corresponding folder
        Needs rewrite ..
        """
        for name, qrFile in sampleQrCodes():
            await ipfsop.sleep()

            if qrFile.exists():
                path = self.app.tempDir.filePath(name)
                if qrFile.copy(path):
                    tmpFile = QFile(path)
                    entry = await ipfsop.addPath(path)
                    await ipfsop.sleep()

                    if not entry:
                        tmpFile.remove()
                        continue

                    exists = await ipfsop.filesLookupHash(
                        model.itemQrCodes.path, entry['Hash'])

                    if not exists:
                        await files.linkEntry(ipfsop, entry,
                                              model.itemQrCodes.path,
                                              entry['Name'])

                    tmpFile.remove()

    def displayItem(self, arg):
        self.itemRoot.appendRow(arg)

    def supportedDropActions(self):
        return Qt.CopyAction | Qt.MoveAction | \
            Qt.TargetMoveAction | Qt.LinkAction

    def mimeData(self, indexes):
        mimedata = QMimeData()

        for idx in indexes:
            if not idx.isValid():
                continue

            nameItem = self.getNameItemFromIdx(idx)

            if nameItem:
                mimedata.setUrls([nameItem.dwebUrl])
                break

        return mimedata

    def canDropMimeData(self, data, action, row, column, parent):
        mimeText = data.text()

        if mimeText and mimeText.startswith('file://'):
            return True
        return False

    def dropMimeData(self, data, action, row, column, parent):
        if data.hasUrls():
            for url in data.urls():
                path = url.toLocalFile()
                if os.path.isfile(path):
                    self.fileDropEvent.emit(path)
                if os.path.isdir(path):
                    self.directoryDropEvent.emit(path)
            return True
        else:
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


def makeFilesModel():
    # Setup the model
    model = FilesItemModel()
    model.setHorizontalHeaderLabels(
        [iFileName(), iFileSize(), iMultihash()])
    return model


class FilesTab(GalacteekTab):
    statusReady = 0
    statusBusy = 1

    def __init__(self, gWindow, **kw):
        super().__init__(gWindow, **kw)

        self.lock = asyncio.Lock()
        self.fmWidget = QWidget()
        self.addToLayout(self.fmWidget)

        self.ui = ui_files.Ui_FileManagerForm()
        self.ui.setupUi(self.fmWidget)
        self.clipboard = self.app.appClipboard
        self.status = self.statusReady

        # Build file browser
        self.displayedItem = None
        self.createFileManager()

        # Connect the various buttons
        self.ui.addFileButton.clicked.connect(self.onAddFilesClicked)
        self.ui.addDirectoryButton.clicked.connect(self.onAddDirClicked)
        self.ui.refreshButton.clicked.connect(self.onRefreshClicked)
        self.ui.searchFiles.returnPressed.connect(self.onSearchFiles)
        self.ui.fileManagerSwitch.clicked.connect(self.onFileManager)
        self.ui.fileManagerButton.clicked.connect(self.onFileManager)

        # Connect the tree view actions
        self.ui.treeFiles.doubleClicked.connect(self.onDoubleClicked)
        self.ui.treeFiles.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.treeFiles.customContextMenuRequested.connect(
            self.onContextMenu)
        self.ui.treeFiles.expanded.connect(self.onExpanded)

        # Path selector
        self.ui.pathSelector.insertItem(0, getIcon('go-home.png'), 'Home')
        self.ui.pathSelector.insertItem(1, getIcon('folder-pictures.png'),
                                        iPictures())
        self.ui.pathSelector.insertItem(2, getIcon('folder-videos.png'),
                                        iVideos())
        self.ui.pathSelector.insertItem(3, getIcon('folder-music.png'),
                                        iMusic())
        self.ui.pathSelector.insertItem(4, getIcon('code-fork.png'), iCode())
        self.ui.pathSelector.insertItem(5, getIcon('folder-documents.png'),
                                        iDocuments())
        self.ui.pathSelector.insertItem(6, getMimeIcon('text/html'),
                                        iWebPages())
        self.ui.pathSelector.insertItem(7, getIcon('ipfs-qrcode.png'),
                                        iQrCodes())
        self.ui.pathSelector.activated.connect(self.onPathSelector)

        # Connect the event filter
        evfilter = IPFSTreeKeyFilter(self.ui.treeFiles)
        evfilter.copyHashPressed.connect(self.onCopyItemHash)
        evfilter.copyPathPressed.connect(self.onCopyItemPath)
        evfilter.returnPressed.connect(self.onReturn)
        evfilter.explorePressed.connect(self.onExploreItem)
        self.ui.treeFiles.installEventFilter(evfilter)

        self.setupModel()

        # Setup the tree view
        self.ui.treeFiles.setExpandsOnDoubleClick(True)
        self.ui.treeFiles.setItemsExpandable(True)
        self.ui.treeFiles.setSortingEnabled(True)
        self.ui.treeFiles.sortByColumn(0, Qt.AscendingOrder)

        if self.app.settingsMgr.hideHashes:
            self.ui.treeFiles.hideColumn(2)

        self.iconFolder = getIcon('folder-open.png')
        self.iconFile = getIcon('file.png')

        # Configure drag-and-drop
        self.ui.treeFiles.setAcceptDrops(True)
        self.ui.treeFiles.setDragDropMode(QAbstractItemView.DragDrop)

        self.ipfsKeys = []

    @property
    def displayPath(self):
        if self.displayedItem:
            return self.displayedItem.path

    @property
    def busy(self):
        return self.status == self.statusBusy

    def createFileManager(self):
        self.fManagerModel = QFileSystemModel()
        self.fManagerModel.setRootPath('')

        self.localTree = QTreeView()
        self.localTree.setModel(self.fManagerModel)
        self.localTree.setDragEnabled(True)
        self.localTree.setDragDropMode(QAbstractItemView.DragOnly)
        self.localTree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.localTree.setItemsExpandable(True)

        rootIndex = self.fManagerModel.index(QDir.rootPath())
        if rootIndex.isValid():
            self.localTree.setRootIndex(rootIndex)

        if self.app.system in ['Linux', 'FreeBSD', 'Darwin']:
            """
            Expand the user's home folder and its parents
            """

            home = QDir(QDir.homePath())
            myHomeIndex = self.fManagerModel.index(home.path())

            if myHomeIndex.isValid():
                self.localTree.expand(myHomeIndex)

                while home.cdUp():
                    idx = self.fManagerModel.index(home.path())
                    if idx.isValid():
                        self.localTree.expand(idx)

        for col in range(1, 4):
            self.localTree.hideColumn(col)

        self.localTree.hide()
        self.ui.hLayoutBrowser.insertWidget(0, self.localTree)

    def setupModel(self):
        # Setup the model, caching it in the profile object
        if self.profile.filesModel:
            self.model = self.profile.filesModel
        else:
            self.model = makeFilesModel()
            self.profile.setFilesModel(self.model)
            self.model.setupItemsFromProfile(self.profile, self.model, self)

        self.ui.treeFiles.setModel(self.model)
        self.ui.treeFiles.header().setSectionResizeMode(
            QHeaderView.ResizeToContents)

        if self.displayedItem is None:
            self.changeDisplayItem(self.model.itemHome)

        self.app.task(self.updateKeys)

        self.disconnectDropSignals()

        # Connect the model's drag-and-drop signals
        self.model.fileDropEvent.connect(self.onDropFile)
        self.model.directoryDropEvent.connect(self.onDropDirectory)

    def enableButtons(self, flag=True):
        for btn in [self.ui.addFileButton,
                    self.ui.addDirectoryButton,
                    self.ui.refreshButton,
                    self.ui.fileManagerSwitch,
                    self.ui.fileManagerButton,
                    self.ui.pathSelector,
                    self.ui.searchFiles]:
            btn.setEnabled(flag)

    def currentItem(self):
        currentIdx = self.ui.treeFiles.currentIndex()
        if currentIdx.isValid():
            return self.model.getNameItemFromIdx(currentIdx)

    def onClose(self):
        if not self.busy:
            self.disconnectDropSignals()
            return True
        return False

    def disconnectDropSignals(self):
        try:
            self.model.fileDropEvent.disconnect(self.onDropFile)
            self.model.directoryDropEvent.disconnect(self.onDropDirectory)
        except Exception:
            pass

    def onFileManager(self):
        if self.localTree.isHidden():
            self.localTree.show()
        else:
            self.localTree.hide()

    def onDropFile(self, path):
        self.scheduleAddFiles([path])

    def onDropDirectory(self, path):
        self.scheduleAddDirectory(path)

    def onCopyItemHash(self):
        currentItem = self.currentItem()
        if currentItem:
            dataHash = self.model.getHashFromIdx(currentItem.index())
            self.app.setClipboardText(dataHash)

    def onCopyItemPath(self):
        currentItem = self.currentItem()
        if currentItem:
            nameItem = self.model.getNameItemFromIdx(currentItem.index())
            if nameItem:
                self.app.setClipboardText(nameItem.fullPath)

    def onReturn(self):
        currentItem = self.currentItem()
        dataHash = self.model.getHashFromIdx(currentItem.index())
        if dataHash:
            self.gWindow.addBrowserTab().browseIpfsHash(dataHash)

    def onExpanded(self, idx):
        pass

    def pathSelectorDefault(self):
        self.ui.pathSelector.setCurrentIndex(0)

    def onPathSelector(self, idx):
        if self.busy:
            return

        text = self.ui.pathSelector.itemText(idx)

        if text == iHome():
            self.changeDisplayItem(self.model.itemHome)
        if text == iPictures():
            self.changeDisplayItem(self.model.itemPictures)
        if text == iVideos():
            self.changeDisplayItem(self.model.itemVideos)
        if text == iMusic():
            self.changeDisplayItem(self.model.itemMusic)
        if text == iCode():
            self.changeDisplayItem(self.model.itemCode)
        if text == iDocuments():
            self.changeDisplayItem(self.model.itemDocuments)
        if text == iWebPages():
            self.changeDisplayItem(self.model.itemWebPages)
        if text == iQrCodes():
            self.changeDisplayItem(self.model.itemQrCodes)

    def changeDisplayItem(self, item):
        self.displayedItem = item
        self.ui.treeFiles.setRootIndex(self.displayedItem.index())
        self.updateTree()
        self.ui.treeFiles.expand(self.displayedItem.index())

    def onContextMenuVoid(self, point):
        menu = QMenu()
        menu.exec(self.ui.treeFiles.mapToGlobal(point))

    def onContextMenu(self, point):
        idx = self.ui.treeFiles.indexAt(point)
        if not idx.isValid():
            return self.onContextMenuVoid(point)

        nameItem = self.model.getNameItemFromIdx(idx)
        dataHash = self.model.getHashFromIdx(idx)
        ipfsPath = joinIpfs(dataHash)
        menu = QMenu()

        def explore(multihash):
            self.gWindow.exploreMultihash(multihash)

        def hashmark(mPath, name):
            addHashmark(self.app.marksLocal, mPath, name)

        def copyHashToClipboard(itemHash):
            self.clipboard.setText(itemHash)

        def openWithMediaPlayer(itemHash):
            parentHash = nameItem.parentHash
            name = nameItem.entry['Name']
            if parentHash:
                fp = joinIpfs(os.path.join(parentHash, name))
                self.gWindow.mediaPlayerPlay(fp, mediaName=name)
            else:
                self.gWindow.mediaPlayerPlay(joinIpfs(itemHash),
                                             mediaName=name)

        menu.addAction(getIcon('clipboard.png'),
                       iCopyMultihashToClipboard(),
                       functools.partial(self.app.setClipboardText, dataHash))
        if nameItem.fullPath:
            menu.addAction(getIcon('clipboard.png'),
                           iCopyPathToClipboard(),
                           functools.partial(self.app.setClipboardText,
                                             nameItem.fullPath))
        menu.addSeparator()
        menu.addAction(iUnlinkFile(), functools.partial(
            self.scheduleUnlink, nameItem, dataHash))
        menu.addAction(iDeleteFile(), functools.partial(
            self.scheduleDelete, nameItem, dataHash))
        menu.addSeparator()
        menu.addAction(getIcon('hashmarks.png'),
                       iHashmarkFile(),
                       functools.partial(hashmark, ipfsPath,
                                         nameItem.entry['Name']))
        menu.addAction(getIconIpfs64(),
                       iBrowseFile(),
                       functools.partial(self.browse, dataHash))
        menu.addAction(getIcon('open.png'),
                       iOpen(),
                       functools.partial(ensure, self.app.resourceOpener.open(
                                         joinIpfs(dataHash))
                                         ))
        if nameItem.isFile():
            menu.addAction(getIcon('text-editor.png'),
                           'Edit',
                           functools.partial(self.editFile,
                                             nameItem.ipfsPath))

        if nameItem.isDir():
            menu.addAction(getIcon('folder-open.png'),
                           iExploreDir(),
                           functools.partial(explore, dataHash))

        def publishToKey(action):
            key = action.data()['key']['Name']
            oHash = action.data()['hash']

            async def publish(op, oHash, keyName):
                await op.publish(joinIpfs(oHash), key=keyName)

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

        menu.addSeparator()
        menu.addMenu(publishMenu)
        menu.exec(self.ui.treeFiles.mapToGlobal(point))

    def browse(self, path):
        self.gWindow.addBrowserTab().browseFsPath(
            IPFSPath(path))

    def editFile(self, ipfsPath):
        self.gWindow.addEditorTab(path=ipfsPath)

    def onExploreItem(self):
        current = self.currentItem()

        if current and current.isDir():
            dataHash = self.model.getHashFromIdx(current.index())
            self.gWindow.exploreMultihash(dataHash)

    def onDoubleClicked(self, idx):
        resourceOpener = self.gWindow.app.resourceOpener

        if not idx.isValid():
            return

        nameItem = self.model.getNameItemFromIdx(idx)
        item = self.model.itemFromIndex(idx)
        dataHash = self.model.getHashFromIdx(idx)

        if nameItem.isFile():
            fileName = nameItem.text()
            finalPath = joinIpfs(dataHash)

            # Find the parent hash
            parentHash = nameItem.parentHash
            if parentHash:
                # We have the parent hash, so use it to build a file path
                # preserving the real file name
                finalPath = joinIpfs(os.path.join(parentHash, fileName))

            ensure(resourceOpener.open(finalPath))

        elif nameItem.isDir():
            self.app.task(self.listFiles, item.path, parentItem=item,
                          autoexpand=True)

    def onSearchFiles(self):
        search = self.ui.searchFiles.text()
        self.ui.treeFiles.keyboardSearch(search)

    def onMkDirClicked(self):
        dirName = QInputDialog.getText(self, 'Directory name',
                                       'Directory name')
        if dirName:
            self.app.task(self.makeDir, self.displayedItem.path,
                          dirName[0])

    def onRefreshClicked(self):
        self.updateTree()
        self.ui.treeFiles.setFocus(Qt.OtherFocusReason)

    def onAddDirClicked(self):
        result = QFileDialog.getExistingDirectory(
            None, iSelectDirectory(), getHomePath(), QFileDialog.ShowDirsOnly)
        if result:
            self.scheduleAddDirectory(result)

    def statusAdded(self, name):
        self.statusSet(iAddedFile(name))

    def statusLoading(self, name):
        self.statusSet(iLoading(name))

    def statusSet(self, msg):
        self.ui.statusLabel.setText(msg)

    def onAddFilesClicked(self):
        self.addFilesDialog()

    def addFilesDialog(self, parent=None):
        if parent is None:
            parent = self.displayPath

        result = QFileDialog.getOpenFileNames(
            None, iSelectFiles(), getHomePath(), '(*.*)')
        if not result:
            return

        self.scheduleAddFiles(result[0], parent=parent)

    def scheduleAddFiles(self, path, parent=None):
        if self.busy:
            return
        if parent is None:
            parent = self.displayPath
        return self.app.task(self.addFiles, path, parent)

    def scheduleAddDirectory(self, path):
        if self.busy:
            return
        return self.app.task(self.addDirectory, path)

    def scheduleUnlink(self, item, multihash):
        reply = questionBox('Unlink',
                            'Do you really want to unlink this item ?')
        if reply:
            ensure(self.unlinkFileFromHash(item, multihash))

    def scheduleDelete(self, item, multihash):
        reply = questionBox(
            'Delete',
            'Do you really want to delete: <b>{}</b>'.format(multihash)
        )
        if reply:
            ensure(self.deleteFromMultihash(item, multihash))

    def updateTree(self):
        self.app.task(self.listFiles, self.displayPath,
                      parentItem=self.displayedItem, maxdepth=1)

    @ipfsOp
    async def updateKeys(self, ipfsop):
        self.ipfsKeys = await ipfsop.keys()

    @ipfsOp
    async def makeDir(self, ipfsop, parent, path):
        await ipfsop.filesMkdir(os.path.join(parent, path))
        self.updateTree()

    @ipfsOp
    async def listFiles(self, ipfsop, path, parentItem, maxdepth=0,
                        autoexpand=False):
        if self.busy:
            return
        self.enableButtons(flag=False)
        self.status = self.statusBusy

        try:
            await asyncio.wait_for(
                self.listPath(ipfsop, path, parentItem,
                              maxdepth=maxdepth, autoexpand=autoexpand), 60)
        except aioipfs.APIError:
            messageBox(iErrNoCx())

        self.enableButtons()
        self.status = self.statusReady

    async def listPath(self, op, path, parentItem, depth=0, maxdepth=1,
                       autoexpand=False):
        if not parentItem or not parentItem.path:
            return

        listing = await op.filesList(path)
        if not listing:
            return

        parentItemSibling = self.model.sibling(parentItem.row(), 2,
                                               parentItem.index())
        parentItemHash = self.model.data(parentItemSibling)

        for entry in listing:
            await asyncio.sleep(0)

            found = False
            for child in parentItem.childrenItems():
                if child.entry['Name'] == entry['Name']:
                    if entry['Hash'] != child.entry['Hash']:
                        # The parent has a child item with the same
                        # filename but a different multihash: this item
                        # was deleted and needs to be purged from the model
                        # to let the new entry show up
                        await modelhelpers.modelDeleteAsync(
                            self.model, child.entry['Hash'])
                        break
                if child.entry['Hash'] == entry['Hash']:
                    found = True
                    break

            if found:
                continue

            if entry['Type'] == 1:  # directory
                icon = self.iconFolder
            else:
                icon = self.iconFile

            nItemName = IPFSNameItem(entry, entry['Name'], icon)
            nItemName.mimeFromDb(self.app.mimeDb)
            nItemName.setParentHash(parentItemHash)
            nItemSize = IPFSItem(sizeFormat(entry['Size']))
            nItemHash = IPFSItem(entry['Hash'])

            if nItemName.mimeTypeName:
                # If we have a better icon matching the file's type..
                mIcon = getMimeIcon(nItemName.mimeTypeName)
                if mIcon:
                    nItemName.setIcon(mIcon)

            # Set its path in the MFS
            nItemName.path = os.path.join(parentItem.path, entry['Name'])

            nItem = [nItemName, nItemSize, nItemHash]

            parentItem.appendRow(nItem)

            if entry['Type'] == 1:  # directory
                if autoexpand is True:
                    self.ui.treeFiles.setExpanded(nItemName.index(), True)
                await asyncio.sleep(0)
                if maxdepth > depth:
                    depth += 1
                    await self.listPath(op,
                                        nItemName.path,
                                        nItemName,
                                        maxdepth=maxdepth, depth=depth)
                    depth -= 1

        if autoexpand is True:
            self.ui.treeFiles.expand(parentItem.index())

    @ipfsOp
    async def deleteFromMultihash(self, ipfsop, item, multihash):
        _dir = os.path.dirname(item.path)

        entry = await ipfsop.filesLookupHash(_dir, multihash)

        if entry:
            # Delete the entry in the MFS directory
            await ipfsop.filesDelete(_dir,
                                     entry['Name'], recursive=True)

            # Purge the item's multihash in the model
            # Purge its parent as well because the parent multihash will change
            await modelhelpers.modelDeleteAsync(self.model, multihash)

            if item.parentHash:
                await modelhelpers.modelDeleteAsync(
                    self.model, item.parentHash)

            ensure(ipfsop.purge(multihash))
            log.debug('{0}: deleted'.format(multihash))

            self.updateTree()
        else:
            log.debug('Did not find multihash {}'.format(multihash))

    @ipfsOp
    async def unlinkFileFromHash(self, op, item, multihash):
        _dir = os.path.dirname(item.path)

        listing = await op.filesList(_dir)
        for entry in listing:
            await op.sleep()
            if entry['Hash'] == multihash:
                await op.filesDelete(_dir, entry['Name'], recursive=True)
                await modelhelpers.modelDeleteAsync(self.model, multihash)

    @ipfsOp
    async def addFiles(self, op, files, parent):
        """ Add every file with an optional wrapper directory """

        wrapEnabled = self.app.settingsMgr.isTrue(
            CFG_SECTION_UI, CFG_KEY_WRAPSINGLEFILES)

        self.enableButtons(flag=False)
        self.status = self.statusBusy

        async def onEntry(entry):
            self.statusAdded(entry['Name'])

        count = 0
        for file in files:
            await op.sleep()

            root = await op.addPath(file, wrap=wrapEnabled,
                                    callback=onEntry)

            if root is None:
                self.statusSet(iFileImportError())
                continue

            base = os.path.basename(file)
            if wrapEnabled is True:
                base += '.dirw'

            await self.linkEntry(op, root, parent, base)
            count += 1

        self.statusSet(iImportedCount(count))
        self.enableButtons()
        self.status = self.statusReady
        self.updateTree()
        return True

    @ipfsOp
    async def addDirectory(self, op, path):
        wrapEnabled = self.app.settingsMgr.isTrue(
            CFG_SECTION_UI, CFG_KEY_WRAPDIRECTORIES)

        self.enableButtons(flag=False)
        self.status = self.statusBusy
        basename = os.path.basename(path)
        dirEntry = None

        async def onEntry(entry):
            self.statusAdded(entry['Name'])

        dirEntry = await op.addPath(path, callback=onEntry,
                                    hidden=True, recursive=True,
                                    wrap=wrapEnabled)

        if not dirEntry:
            # Nothing went through ?
            self.enableButtons()
            return False

        if wrapEnabled is True:
            basename += '.dirw'

        await self.linkEntry(op, dirEntry, self.displayPath, basename)

        self.enableButtons()
        self.status = self.statusReady
        self.updateTree()
        return True

    async def linkEntry(self, op, entry, dest, basename):
        for lIndex in range(0, 16):
            await op.sleep()
            if lIndex == 0:
                lNew = basename
            else:
                lNew = '{0}.{1}'.format(basename, lIndex)
            lookup = await op.filesLookup(dest, lNew)
            if not lookup:
                linkS = await op.filesLink(entry, dest, name=lNew)
                if linkS:
                    return lNew
