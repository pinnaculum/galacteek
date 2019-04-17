import os.path
import aioipfs

from PyQt5.QtWidgets import QStackedWidget
from PyQt5.QtWidgets import QToolButton
from PyQt5.QtWidgets import QMenu
from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QApplication

from PyQt5.QtGui import QKeySequence

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import QSize
from PyQt5.QtCore import QUrl

from galacteek import ensure
from galacteek.core.clipboard import ClipboardItem
from galacteek.ipfs.cidhelpers import stripIpfs
from galacteek.ipfs.mimetype import isDirectoryMtype
from galacteek.ipfs import ipfsOp

from .hashmarks import addHashmark
from .helpers import getMimeIcon
from .helpers import getIcon
from .helpers import getIconIpfsIce
from .helpers import messageBox
from .helpers import getIconFromIpfs
from .helpers import runDialog
from .widgets import PopupToolButton
from .dialogs import ChooseProgramDialog

from . import dag

from .i18n import iUnknown
from .i18n import iDagViewer


def iClipboardEmpty():
    return QCoreApplication.translate(
        'clipboardManager',
        'No valid IPFS CID/path in the clipboard')


def iFromClipboard(path):
    return QCoreApplication.translate(
        'clipboardManager',
        'Clipboard: browse IPFS path: {0}').format(path)


def iClipboardClearHistory():
    return QCoreApplication.translate(
        'clipboardManager',
        'Clear clipboard history')


def iClipLoaderExplore(path):
    return QCoreApplication.translate('clipboardManager',
                                      'Explore directory: {0}').format(path)


def iClipLoaderHashmark(path):
    return QCoreApplication.translate('clipboardManager',
                                      'Hashmark: {0}').format(path)


def iClipLoaderPin(path):
    return QCoreApplication.translate('clipboardManager',
                                      'Pin: {0}').format(path)


def iClipLoaderIpldExplorer(path):
    return QCoreApplication.translate('clipboardManager',
                                      'Run IPLD Explorer: {0}').format(path)


def iClipLoaderDagView(path):
    return QCoreApplication.translate('clipboardManager',
                                      'DAG view: {0}').format(path)


def iClipboardHistory():
    return QCoreApplication.translate('clipboardManager', 'Clipboard history')


def iClipLoaderBrowse(path):
    return QCoreApplication.translate('clipboardManager',
                                      'Browse IPFS path: {0}').format(path)


def iClipItemOpen():
    return QCoreApplication.translate('clipboardManager', 'Open')


def iClipItemOpenWithApp():
    return QCoreApplication.translate('clipboardManager',
                                      'Open with application')


def iClipItemOpenWithDefaultApp():
    return QCoreApplication.translate('clipboardManager',
                                      'Open with default system application')


def iClipItemSetCurrent():
    return QCoreApplication.translate('clipboardManager',
                                      'Set as current clipboard item')


def iClipItemRemove():
    return QCoreApplication.translate('clipboardManager',
                                      'Remove item')


def iClipItemSwitch(num):
    return QCoreApplication.translate(
        'clipboardManager',
        'Switch to item {} in the stack').format(num)


def iClipboardStack():
    return QCoreApplication.translate('clipboardManager',
                                      'Clipboard stack')


class ClipboardManager(PopupToolButton):
    def __init__(self, clipTracker, itemsStack, rscOpener,
                 icon=None, menu=None, parent=None):
        super().__init__(icon=icon, menu=menu, parent=parent,
                         mode=QToolButton.InstantPopup)

        self.app = QApplication.instance()
        self.tracker = clipTracker
        self.itemsStack = itemsStack
        self.rscOpener = rscOpener

        self.setAcceptDrops(True)
        self.setObjectName('clipboardManager')
        self.setToolTip(iClipboardEmpty())

        self.tracker.currentItemChanged.connect(self.itemChanged)
        self.tracker.itemAdded.connect(self.itemAdded)

        self.menu.setToolTipsVisible(True)

        self.itSwitchMenu = QMenu(iClipboardStack())
        self.itSwitchMenu.triggered.connect(self.onItemSwitch)

        for num in range(1, 10):
            action = QAction(getIcon('clipboard.png'),
                             iClipItemSwitch(num),
                             self,
                             shortcut=QKeySequence('Ctrl+' + str(num))
                             )
            action.setData(num)
            self.itSwitchMenu.addAction(action)

        self.initHistoryMenu()

    def onItemSwitch(self, action):
        num = action.data()

        if isinstance(num, int):
            button = self.itemsStack.getStackItem(num)
            if button:
                self.tracker.current = button.item

    def initHistoryMenu(self):
        self.menu.clear()
        self.menu.addAction(iClipboardClearHistory(),
                            self.onHistoryClear)
        self.menu.addSeparator()
        self.menu.addMenu(self.itSwitchMenu)
        self.menu.addSeparator()

    def onHistoryClear(self):
        self.initHistoryMenu()
        self.tracker.clearHistory()

    def onHistoryItemClicked(self, action):
        item = action.data()

        if item:
            if action.text() == iClipItemOpen():
                ensure(self.rscOpener.open(item.path, item.mimeType))
            elif action.text() == iClipItemSetCurrent():
                self.tracker.current = item
            elif action.text() == iClipItemRemove():
                self.tracker.removeItem(item)

    def itemAdded(self, item):
        shortened = os.path.basename(item.path)

        nMenu = QMenu(shortened, self)
        nMenu.setToolTipsVisible(True)
        nMenu.setToolTip(item.path)
        nMenu.triggered.connect(self.onHistoryItemClicked)
        self.menu.addMenu(nMenu)

        actionOpen = QAction(iClipItemOpen(), self)
        actionOpen.setToolTip(item.path)
        actionOpen.setData(item)

        actionSetCurrent = QAction(iClipItemSetCurrent(), self)
        actionSetCurrent.setData(item)
        actionSetCurrent.setToolTip(item.path)

        nMenu.addAction(actionOpen)
        nMenu.addAction(actionSetCurrent)

        def changeIcons(item, nMenu, aOpen):
            nMenu.setIcon(item.mimeIcon)
            aOpen.setIcon(item.mimeIcon)

        item.mimeIconAvailable.connect(
            lambda: changeIcons(item, nMenu, actionOpen))

    def itemChanged(self, item):
        self.itemsStack.activateItem(item)

    def dragEnterEvent(self, event):
        mimeData = event.mimeData()

        if mimeData.hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        """
        Process drag-and-drops of URLs pointing to an IPFS resource

        Remove the query & fragment in the URL before passing it to the
        clipboard processor
        """

        mimeData = event.mimeData()

        if mimeData.hasUrls():
            for url in mimeData.urls():
                self.tracker.clipboardProcess(url.toString(
                    QUrl.RemoveQuery | QUrl.RemoveFragment
                ))

        event.acceptProposedAction()


class ClipboardItemButton(PopupToolButton):
    """
    Represents a ClipboardItem in the clipboard stack
    """
    def __init__(self, rscOpener, clipItem=None, *args, **kw):
        super().__init__(*args, **kw)

        self.app = QApplication.instance()
        self.setObjectName('currentClipItem')
        self.setIcon(getMimeIcon('unknown'))
        self.setIconSize(QSize(32, 32))
        self.setToolTip(iClipboardEmpty())
        self.setEnabled(False)
        self.rscOpener = rscOpener

        if clipItem:
            self.setClipboardItem(clipItem)
        else:
            self._item = None

        self.clicked.connect(self.onOpen)

        self.hashmarkAction = QAction(getIcon('hashmarks.png'),
                                      iClipboardEmpty(), self,
                                      triggered=self.onHashmark)

        self.openAction = QAction(getIcon('terminal.png'),
                                  iClipboardEmpty(), self,
                                  shortcut=QKeySequence('Ctrl+o'),
                                  triggered=self.onOpen)

        self.openWithAppAction = QAction(getIcon('terminal.png'),
                                         iClipItemOpenWithApp(), self,
                                         triggered=self.onOpenWithProgram)

        self.openWithDefaultAction = QAction(
            getIcon('terminal.png'),
            iClipItemOpenWithDefaultApp(),
            self,
            triggered=self.onOpenWithDefaultApp)

        self.exploreHashAction = QAction(
            getIconIpfsIce(),
            iClipboardEmpty(), self,
            shortcut=QKeySequence('Ctrl+e'),
            triggered=self.onExplore)

        self.dagViewAction = QAction(
            getIcon('ipld-logo.png'),
            iClipboardEmpty(), self,
            shortcut=QKeySequence('Ctrl+g'),
            triggered=self.onDagView)

        self.ipldExplorerAction = QAction(
            getIcon('ipld-logo.png'),
            iClipboardEmpty(), self,
            shortcut=QKeySequence('Ctrl+i'),
            triggered=self.onIpldExplore)

        self.pinAction = QAction(
            getIcon('pin-black.png'),
            iClipboardEmpty(), self,
            shortcut=QKeySequence('Ctrl+p'),
            triggered=self.onPin)

    @property
    def item(self):
        return self._item

    def setClipboardItem(self, item):
        self.setEnabled(True)
        self._item = item

        if item.mimeIcon:
            # Already set icon from mimetype
            self.setIcon(item.mimeIcon)
            self.updateButton()
        else:
            item.mimeTypeDetected.connect(
                lambda mType: self.updateButton())

    def onHashmark(self):
        if self.item:
            addHashmark(self.app.marksLocal, self.item.path,
                        self.item.basename)

    def onOpenWithProgram(self):
        def onAccept(dlg):
            prgValue = dlg.textValue()
            if len(prgValue) > 0:
                ensure(self.rscOpener.openWithExternal(
                    self.item.cid, prgValue.split()))

        runDialog(ChooseProgramDialog, accepted=onAccept)

    def onOpenWithDefaultApp(self):
        if self.item.cid:
            ensure(self.rscOpener.openWithSystemDefault(self.item.cid))

    def updateButton(self):
        if not isinstance(self.item, ClipboardItem):
            return

        self.menu.clear()
        self.menu.addAction(self.openAction)
        self.menu.addAction(self.openWithAppAction)
        self.menu.addAction(self.openWithDefaultAction)
        self.menu.addSeparator()
        self.menu.addAction(self.hashmarkAction)
        self.menu.addAction(self.dagViewAction)
        self.menu.addAction(self.ipldExplorerAction)
        self.menu.addAction(self.pinAction)

        if isDirectoryMtype(self.item.mimeType):
            # It's a directory. Add the explore action and disable
            # the actions that don't apply to a folder
            self.menu.addAction(self.exploreHashAction)
            self.openWithAppAction.setEnabled(False)
            self.openWithDefaultAction.setEnabled(False)

        self.exploreHashAction.setText(iClipLoaderExplore(self.item.path))
        self.openAction.setText(iClipItemOpen())
        self.dagViewAction.setText(iClipLoaderDagView(self.item.path))
        self.hashmarkAction.setText(iClipLoaderHashmark(self.item.path))
        self.ipldExplorerAction.setText(
            iClipLoaderIpldExplorer(self.item.path))
        self.pinAction.setText(iClipLoaderPin(self.item.path))

        self.setToolTip('{path} (type: {mimetype})'.format(
            path=self.item.path,
            mimetype=self.item.mimeType if self.item.mimeType else iUnknown()
        ))

        if not self.item.mimeType:
            return self.setIcon(getMimeIcon('unknown'))

        icon = getMimeIcon(self.item.mimeType)
        if icon:
            self.item.mimeIcon = icon
            self.setIcon(icon)
        else:
            mIconFile = None

            if self.item.mimeType == 'application/x-directory':
                mIconFile = 'inode/directory'
            if self.item.mimeCategory == 'text':
                mIconFile = 'text/plain'
            if self.item.mimeCategory == 'image':
                mIconFile = 'image/x-generic'
                ensure(self.prefetchImage())
            if self.item.mimeCategory == 'video':
                mIconFile = 'video/x-generic'
            if self.item.mimeCategory == 'audio':
                mIconFile = 'audio/x-generic'

            icon = getMimeIcon(mIconFile if mIconFile else 'unknown')
            if icon:
                self.item.mimeIcon = icon
                self.setIcon(icon)

    @ipfsOp
    async def prefetchImage(self, ipfsop):
        try:
            icon = await ipfsop.waitFor(
                getIconFromIpfs(ipfsop, self.item.path), 10
            )
        except aioipfs.APIError:
            pass
        else:
            if icon:
                self.setIcon(icon)

    def onOpen(self):
        if self.item:
            ensure(self.rscOpener.open(self.item.path, self.item.mimeType))

    def onExplore(self):
        if self.item and self.item.cid:
            self.app.mainWindow.exploreMultihash(self.item.cid)

    def onDagView(self):
        if self.item:
            view = dag.DAGViewer(self.item.path, self.app.mainWindow)
            self.app.mainWindow.registerTab(
                view, iDagViewer(),
                current=True,
                icon=getIcon('ipld.png'),
                tooltip=self.item.path
            )
        else:
            messageBox(iClipboardEmpty())

    def onIpldExplore(self):
        """
        Open the IPLD explorer application for the CID in the clipboard
        """
        if self.item:
            mPath, mark = self.app.marksLocal.searchByMetadata({
                'title': 'IPLD explorer'})
            if mark:
                link = os.path.join(
                    mPath, '#', 'explore', stripIpfs(self.item.path))
                self.app.mainWindow.addBrowserTab().browseFsPath(link)

    def onPin(self):
        if self.item:
            ensure(self.app.ipfsCtx.pin(self.item.path, True, None,
                                        qname='clipboard'))


class ClipboardItemsStack(QStackedWidget):
    """
    Stacked widget responsible for displaying tool buttons for every
    clipboard item
    """

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

        self.app = QApplication.instance()
        self.app.clipTracker.itemRemoved.connect(self.onItemRemoved)
        self.setObjectName('currentClipItem')
        self.rscOpener = self.app.resourceOpener
        self.setFixedSize(40, 32)
        self.addItemButton()

    def onItemRemoved(self, item):
        for idx in range(0, self.count() + 1):
            button = self.widget(idx)
            if button and button.item == item:
                self.removeWidget(button)

    def findButtonByClipItem(self, item):
        for idx in range(1, self.count() + 1):
            button = self.widget(idx)
            if button and button.item == item:
                return button

    def addItemButton(self, item=None):
        """
        Add a button for a clipboard item on the stack and return it
        """
        button = ClipboardItemButton(
            self.rscOpener,
            clipItem=item,
            parent=self
        )
        self.addWidget(button)
        return button

    def activateItem(self, item):
        """
        Create a tool button for a clipboard item if not registered yet,
        or set it as the current widget of the stack otherwise
        """
        btn = self.findButtonByClipItem(item)
        if not btn:
            button = self.addItemButton(item=item)
            self.setCurrentWidget(button)
        else:
            self.setCurrentWidget(btn)

    def popupStackItem(self, itemNo):
        itemIdx = self.count() - itemNo

        if itemIdx > 0:
            button = self.widget(itemIdx)
            if button:
                self.setCurrentWidget(button)
                return button

    def getStackItem(self, itemNo):
        itemIdx = self.count() - itemNo

        if itemIdx > 0:
            return self.widget(itemIdx)
