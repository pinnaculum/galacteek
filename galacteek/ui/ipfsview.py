import os.path

from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QTreeView
from PyQt5.QtWidgets import QHeaderView
from PyQt5.QtWidgets import QToolBox
from PyQt5.QtWidgets import QTextBrowser
from PyQt5.QtWidgets import QProgressBar
from PyQt5.QtWidgets import QSpacerItem
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QToolButton
from PyQt5.QtWidgets import QAbstractItemView

from PyQt5.QtGui import QStandardItemModel
from PyQt5.QtGui import QKeySequence

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QEvent
from PyQt5.QtCore import QObject
from PyQt5.QtCore import pyqtSignal

from galacteek.appsettings import *
from galacteek.ipfs import cidhelpers
from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.wrappers import ipfsOp, ipfsStatOp
from galacteek.ipfs.cache import IPFSEntryCache
from galacteek.ipfs.mimetype import detectMimeTypeFromBuffer
from galacteek.ipfs.cidhelpers import joinIpfs
from galacteek import ensure

from .i18n import *
from .helpers import *
from .widgets import GalacteekTab
from .hashmarks import *

import aioipfs


def iCIDInfo(cidv, linksCount, size):
    return QCoreApplication.translate(
        'IPFSHashExplorer',
        'CID (v{0}): {1} links, total size: {2}').format(
        cidv,
        linksCount,
        size)


def iGitClone():
    return QCoreApplication.translate('IPFSHashExplorer',
                                      'Clone repository')


def iGitClonedRepo(path):
    return QCoreApplication.translate(
        'IPFSHashExplorer',
        'Cloned git repository: {0}').format(path)


def iGitErrorCloning(msg):
    return QCoreApplication.translate(
        'IPFSHashExplorer',
        'Error cloning git repository: {0}').format(msg)


def iGitInvalid():
    return QCoreApplication.translate('IPFSHashExplorer',
                                      'Invalid git repository')


def iLoading():
    return QCoreApplication.translate('IPFSHashExplorer', 'Loading ...')


def iTimeout():
    return QCoreApplication.translate('IPFSHashExplorer',
                                      'Timeout error')


def iTimeoutTryNoResolve():
    return QCoreApplication.translate(
        'IPFSHashExplorer',
        'Timeout error: trying without resolving nodes types ..')


def iTimeoutInvalidHash():
    return QCoreApplication.translate('IPFSHashExplorer',
                                      'Timeout error: invalid hash')


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

        self._entry = entry
        self._mimeType = None

    @property
    def entry(self):
        return self._entry

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

    def cid(self):
        return cidhelpers.getCID(self.entry['Hash'])

    def getFullPath(self):
        """
        Returns the full IPFS path of the entry associated with this item
        (preserving file names) if we have the parent's hash, or the IPFS path
        with the entry's hash otherwise
        """
        parentHash = self.getParentHash()
        name = self.entry['Name']
        if parentHash:
            return joinIpfs(os.path.join(parentHash, name))
        else:
            return joinIpfs(self.entry['Hash'])

    def isRaw(self):
        return self.entry['Type'] == 0

    def isDir(self):
        return self.entry['Type'] == 1

    def isFile(self):
        return self.entry['Type'] == 2

    def isMetadata(self):
        return self.entry['Type'] == 3

    def isSymlink(self):
        return self.entry['Type'] == 4

    def isUnknown(self):
        return self.entry['Type'] == -1


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
        for itNum in range(first, last + 1):
            itNameIdx = self.index(itNum, self.COL_NAME, parent)
            itName = self.itemFromIndex(itNameIdx)
            entry = itName.entry
            self.entryCache.register(entry)


class IPFSHashExplorerToolBox(GalacteekTab):
    """
    Organizes IPFSHashExplorerWidgets with a QToolBox
    """

    def __init__(self, gWindow, hashRef, maxItems=16, parent=None):
        super(IPFSHashExplorerToolBox, self).__init__(gWindow)

        self.rootHash = hashRef
        self.maxItems = maxItems

        self.toolbox = QToolBox()
        self.exLayout = QVBoxLayout()
        self.exLayout.addWidget(self.toolbox)

        self.vLayout.addLayout(self.exLayout)
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

        view = IPFSHashExplorerWidget(self.gWindow, hashRef,
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


class TextViewerTab(GalacteekTab):
    def __init__(self, parent=None):
        super(TextViewerTab, self).__init__(parent)

        self.textLayout = QVBoxLayout()
        self.textBrowser = QTextBrowser()

        self.textLayout.addWidget(self.textBrowser)
        self.vLayout.addLayout(self.textLayout)

    def show(self, ipfsPath):
        ensure(self.showFromPath(ipfsPath))

    @ipfsOp
    async def showFromPath(self, ipfsop, ipfsPath):
        data = await ipfsop.client.cat(ipfsPath)

        if not data:
            return messageBox('File could not be read')

        textData = self.decode(data)

        mType = await detectMimeTypeFromBuffer(data)

        if mType == 'text/html':
            self.textBrowser.setHtml(textData)
        else:
            self.textBrowser.setPlainText(textData)

    def decode(self, data):
        for enc in ['utf-8', 'latin1', 'ascii']:
            try:
                textData = data.decode(enc)
            except BaseException:
                continue
            else:
                return textData


class HashTreeView(QTreeView):
    pass


class IPFSHashExplorerWidget(QWidget):
    def __init__(self, gWindow, hashRef, addClose=False,
                 autoOpenFolders=False, parent=None):
        super(IPFSHashExplorerWidget, self).__init__(parent)

        self.parent = parent

        self.gWindow = gWindow
        self.app = gWindow.app
        self.rootHash = hashRef
        self.rootPath = joinIpfs(self.rootHash)
        self.cid = cidhelpers.getCID(self.rootHash)

        self.mainLayout = QVBoxLayout(self)
        self.setLayout(self.mainLayout)

        self.autoOpenFolders = autoOpenFolders
        self.hLayoutTop = QHBoxLayout()
        self.hLayoutInfo = QHBoxLayout()
        self.hLayoutCtrl = QHBoxLayout()
        self.hLayoutTop.addLayout(self.hLayoutInfo)
        spacerItem = QSpacerItem(10, 20, QSizePolicy.Expanding,
                                 QSizePolicy.Minimum)
        self.hLayoutTop.addItem(spacerItem)
        self.hLayoutTop.addLayout(self.hLayoutCtrl)

        self.labelInfo = QLabel()

        self.hLayoutInfo.addWidget(self.labelInfo, 0, Qt.AlignLeft)

        if addClose:
            self.closeButton = QPushButton('Close')
            self.closeButton.clicked.connect(self.onCloseView)
            self.closeButton.setMaximumWidth(100)
            self.closeButton.setShortcut(QKeySequence('Ctrl+w'))
            self.hLayoutCtrl.addWidget(self.closeButton, 0, Qt.AlignLeft)

        self.getTask = None
        self.getButton = QPushButton(iDownload())
        self.getButton.clicked.connect(self.onGet)
        self.getButton.setShortcut(QKeySequence('Ctrl+d'))
        self.getLabel = QLabel()
        self.getProgress = QProgressBar()
        self.getProgress.setMinimum(0)
        self.getProgress.setMaximum(100)
        self.getProgress.hide()

        self.markButton = QPushButton(getIcon('hashmarks.png'), iHashmark())
        self.markButton.clicked.connect(self.onHashmark)

        self.pinButton = QPushButton('Pin')
        self.pinButton.clicked.connect(self.onPin)

        self.hLayoutCtrl.addWidget(self.getButton)
        self.hLayoutCtrl.addWidget(self.pinButton)
        self.hLayoutCtrl.addWidget(self.markButton)
        self.hLayoutCtrl.addWidget(self.getLabel)
        self.hLayoutCtrl.addWidget(self.getProgress)

        self.mainLayout.addLayout(self.hLayoutTop)

        self.tree = HashTreeView()
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setDragDropMode(QAbstractItemView.DragOnly)
        self.mainLayout.addWidget(self.tree)

        self.model = IPFSHashItemModel(self)
        self.model.setHorizontalHeaderLabels(
            [iFileName(), iFileSize(), iMimeType(), iMultihash()])
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
        self.iconUnknown = getIcon('unknown-file.png')

        self.updateTree()

    def setInfo(self, text):
        self.labelInfo.setText(text)

    def reFocus(self):
        self.tree.setFocus(Qt.OtherFocusReason)

    @ipfsOp
    async def gitClone(self, ipfsop, entry, dest):
        """
        Clone the git repository contained within entry, to directory dest
        """
        from git.repo import base
        from git.exc import InvalidGitRepositoryError

        self.gitButton.setEnabled(False)

        getRet = await ipfsop.client.get(entry['Hash'],
                                         dstdir=self.app.tempDir.path())
        if not getRet:
            self.gitButton.setEnabled(True)
            return messageBox('Could not fetch the git repository')

        repoPath = os.path.join(self.app.tempDir.path(), entry['Hash'])
        try:
            repo = base.Repo(repoPath)
        except InvalidGitRepositoryError:
            return messageBox(iGitInvalid())

        dstPath = '{}.git'.format(
            os.path.join(dest, self.rootHash))

        # Clone it now. No need to run it in a threadpool since the git module
        # will run a git subprocess for the cloning
        try:
            repo.clone(dstPath)
        except Exception as e:
            self.gitButton.setEnabled(True)
            return messageBox(iGitErrorCloning(str(e)))

        messageBox(iGitClonedRepo(dstPath))
        self.gitButton.setEnabled(True)

    def addGitControl(self, gitEntry):
        """
        Adds a tool button for making operations on the git repo
        """
        def clone(entry):
            dirSel = directorySelect()
            if dirSel:
                self.app.task(self.gitClone, entry, dirSel)

        self.gitMenu = QMenu()
        self.gitMenu.addAction(iGitClone(), lambda: clone(gitEntry))
        self.gitButton = QToolButton()
        self.gitButton.setText('Git')
        self.gitButton.setMenu(self.gitMenu)
        self.gitButton.setPopupMode(QToolButton.MenuButtonPopup)
        self.hLayoutCtrl.addWidget(self.gitButton)

    def onHashmark(self):
        addHashmark(self.app.marksLocal,
                    self.rootPath, '',
                    stats=self.app.ipfsCtx.objectStats.get(
                        self.rootPath, {}))

    def onGet(self):
        dirSel = directorySelect()
        if dirSel:
            self.getTask = self.app.task(self.getResource, self.rootPath,
                                         dirSel)

    def onPin(self):
        self.app.task(self.app.ipfsCtx.pinner.queue, self.rootPath, True,
                      None)

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

    def onCloseView(self):
        self.parent.remove(self)

    def browse(self, hash):
        self.gWindow.addBrowserTab().browseIpfsHash(hash)

    def browseFs(self, path):
        self.gWindow.addBrowserTab().browseFsPath(path)

    def onDoubleClicked(self, idx):
        nameItem = self.model.getNameItemFromIdx(idx)
        dataHash = self.model.getHashFromIdx(idx)

        if nameItem.isDir():
            self.parent.viewHash(dataHash, addClose=True)
        elif nameItem.isFile() or nameItem.isUnknown():
            self.openFile(nameItem, dataHash)

    def openFile(self, item, fileHash):
        if item.mimeTypeName is None or item.mimeTypeName == 'text/html':
            return self.browse(fileHash)

        self.gWindow.app.task(self.openWithRscOpener, item, fileHash)

    @ipfsOp
    async def openWithRscOpener(self, ipfsop, item, fileHash):
        # Pass a null mimetype to the resource opener so that it
        # redetects the mimetype with a full (but slower) mime detection method
        opener = self.gWindow.app.resourceOpener
        await opener.open(item.getFullPath(), None)

    def updateTree(self):
        self.app.task(self.listMultihash, self.rootPath,
                      parentItem=self.itemRoot)

    def onContextMenu(self, point):
        selModel = self.tree.selectionModel()
        rows = selModel.selectedRows()

        items = [self.model.getNameItemFromIdx(idx) for idx in rows]

        menu = QMenu()

        def pinRecursive():
            for item in items:
                fp = item.getFullPath()
                self.app.task(self.app.ipfsCtx.pinner.queue, fp, True, None)

        def queueMedia():
            for item in items:
                self.gWindow.mediaPlayerQueue(item.getFullPath())

        def download():
            dirSel = directorySelect()
            for item in items:
                self.app.task(self.getResource, item.getFullPath(),
                              dirSel)

        menu.addAction(getIcon('pin-black.png'), iPinRecursive(),
                       lambda: pinRecursive())
        menu.addAction(getIcon('multimedia.png'), 'Queue in media player',
                       lambda: queueMedia())
        menu.addAction(iDownload(), lambda: download())

        menu.exec(self.tree.mapToGlobal(point))

    async def timedList(self, ipfsop, objPath, parentItem, autoexpand,
                        secs, resolve_type):
        return await asyncio.wait_for(
            self.list(ipfsop, objPath,
                      parentItem=parentItem, autoexpand=autoexpand,
                      resolve_type=resolve_type), secs)

    @ipfsOp
    async def listMultihash(self, ipfsop, objPath, parentItem,
                            autoexpand=False):
        """ Lists contents of IPFS object referenced by objPath,
            and change the tree's model afterwards.

            We first try with resolve-type set to true, and if that gets a
            timeout do the same call but without resolving nodes types
        """

        try:
            self.setInfo(iLoading())
            await self.timedList(ipfsop, objPath, parentItem,
                                 autoexpand, 15, True)
        except asyncio.TimeoutError:
            self.setInfo(iTimeoutTryNoResolve())

            try:
                await self.timedList(ipfsop, objPath, parentItem,
                                     autoexpand, 10, False)
            except asyncio.TimeoutError:
                # That's a dead end .. bury that hash please ..
                self.setInfo(iTimeoutInvalidHash())
                return

        except aioipfs.APIError:
            self.setInfo(iErrNoCx())
            return

        self.tree.setModel(self.model)
        self.tree.header().setSectionResizeMode(self.model.COL_NAME,
                                                QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(self.model.COL_MIME,
                                                QHeaderView.ResizeToContents)
        self.tree.sortByColumn(self.model.COL_NAME, Qt.AscendingOrder)

        if self.app.settingsMgr.hideHashes:
            self.tree.hideColumn(self.model.COL_HASH)

        rStat = await ipfsop.objStatCtxUpdate(objPath)

        if rStat and self.cid:
            self.setInfo(iCIDInfo(self.cid.version,
                                  rStat['NumLinks'],
                                  sizeFormat(rStat['CumulativeSize'])))

    async def list(self, op, path, parentItem=None,
                   autoexpand=False, resolve_type=True):

        parentItemSibling = self.model.sibling(parentItem.row(),
                                               self.model.COL_HASH,
                                               parentItem.index())
        parentItemHash = self.model.data(parentItemSibling)
        if parentItemHash is None:
            parentItemHash = self.rootHash

        async for obj in op.list(path, resolve_type):
            for entry in obj['Links']:
                await op.sleep()

                if entry['Hash'] in self.model.entryCache:
                    continue

                nItemName = IPFSNameItem(entry, entry['Name'], None)
                nItemName.mimeFromDb(self.app.mimeDb)
                nItemName.setParentHash(parentItemHash)
                nItemSize = IPFSItem(sizeFormat(entry['Size']))
                nItemSize.setToolTip(str(entry['Size']))
                nItemMime = IPFSItem(nItemName.mimeTypeName or iUnknown())
                nItemHash = IPFSItem(entry['Hash'])
                nItemName.setToolTip(entry['Hash'])

                if nItemName.isDir():
                    nItemName.setIcon(self.iconFolder)
                elif nItemName.isFile():
                    nItemName.setIcon(self.iconFile)
                elif nItemName.isUnknown():
                    nItemName.setIcon(self.iconUnknown)

                nItem = [nItemName, nItemSize, nItemMime, nItemHash]
                parentItem.appendRow(nItem)

                if nItemName.isDir() and self.autoOpenFolders:
                    # Automatically open sub folders. Used by unit tests
                    self.parent.viewHash(
                        entry['Hash'],
                        addClose=True,
                        autoOpenFolders=self.autoOpenFolders)

                if nItemName.isDir() and entry['Name'] == '.git':
                    # If there's a git repo here, add a control button
                    self.addGitControl(entry)

    @ipfsStatOp
    async def getResource(self, ipfsop, rPath, dest, rStat):
        """
        Get the resource referenced by rPath to directory dest
        """

        if rStat is None:
            return

        self.getProgress.show()
        cumulative = rStat['CumulativeSize']

        async def onGetProgress(ref, bytesRead, arg):
            per = int((bytesRead * 100) / cumulative)
            self.getLabel.setText('Downloaded: {0}'.format(
                sizeFormat(bytesRead)))
            self.getProgress.setValue(per)

        await ipfsop.client.get(rPath, dstdir=dest,
                                progress_callback=onGetProgress,
                                chunk_size=32768)

        self.getLabel.setText('Download finished')
        self.getProgress.hide()
