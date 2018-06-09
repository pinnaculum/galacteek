
import sys
import time
import os.path
import copy

from PyQt5.QtWidgets import (QApplication, QMainWindow,
        QDialog, QLabel, QTextEdit, QPushButton, QVBoxLayout,
        QSystemTrayIcon, QMenu, QAction, QActionGroup, QToolButton,
        QTreeView, QHeaderView, QInputDialog)
from PyQt5.QtCore import (QCoreApplication, QUrl, QBuffer, QIODevice, Qt,
    QTimer, QFile)
from PyQt5.QtCore import pyqtSignal, QUrl, QObject, QDateTime
from PyQt5 import QtWebEngineWidgets, QtWebEngine, QtWebEngineCore
from PyQt5.QtGui import (QClipboard, QPixmap, QIcon, QKeySequence,
        QStandardItemModel, QStandardItem)

from galacteek.ui import mediaplayer
from galacteek.ipfs.wrappers import *
from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.cidhelpers import cidValid
from . import ui_galacteek
from . import browser, files, keys, settings, bookmarks, textedit, ipfsview
from .helpers import *
from .modelhelpers import *
from .widgets import GalacteekTab
from .dialogs import *
from ..appsettings import *
from .i18n import *

def iHashmarks():
    return QCoreApplication.translate('GalacteekWindow', 'Hashmarks')
def iFileManager():
    return QCoreApplication.translate('GalacteekWindow', 'File Manager')
def iKeys():
    return QCoreApplication.translate('GalacteekWindow', 'IPFS Keys')

def iFromClipboard(path):
    return QCoreApplication.translate('GalacteekWindow',
        'Clipboard: browse IPFS path: {0}').format(path)

def iClipboardEmpty():
    return QCoreApplication.translate('GalacteekWindow',
        'No valid IPFS CID/path in the clipboard')

def iClipLoaderExplore(path):
    return QCoreApplication.translate('GalacteekWindow',
        'Explore IPFS path: {0}').format(path)

def iClipboardHistory():
    return QCoreApplication.translate('GalacteekWindow', 'Clipboard history')

def iNewProfile():
    return QCoreApplication.translate('GalacteekWindow', 'New Profile')

def iSwitchedProfile():
    return QCoreApplication.translate('GalacteekWindow',
            'Successfully switched profile')

def iClipLoaderBrowse(path):
    return QCoreApplication.translate('GalacteekWindow',
        'Browse IPFS path: {0}').format(path)

def iPinningItemStatus(pinPath, pinProgress):
    return QCoreApplication.translate('GalacteekWindow',
        '\nPath: {0}, nodes processed: {1}').format(pinPath, pinProgress)

def iAbout():
    from galacteek import __version__
    return QCoreApplication.translate('GalacteekWindow', '''
        <p><b>Galacteek</b> is a simple IPFS browser and content publisher
        </p>
        <p>Author: David Ferlier</p>
        <p>Galacteek version {0}</p>''').format(__version__)

class PinStatusDetails(GalacteekTab):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

        self.tree = QTreeView(self)
        self.vLayout = QVBoxLayout(self)
        self.vLayout.addWidget(self.tree)

        self.app.ipfsCtx.pinItemStatusChanged.connect(self.onPinStatusChanged)
        self.app.ipfsCtx.pinFinished.connect(self.onPinFinished)

        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(
            ['Path', 'Nodes processed'])

        self.tree.setModel(self.model)
        self.tree.header().setSectionResizeMode(0,
                QHeaderView.ResizeToContents)

    def findPinItems(self, path):
        ret = modelSearch(self.model,
                search=path, columns=[0])
        if len(ret) == 0:
            return None, None
        itemP = self.model.itemFromIndex(ret.pop())
        idxS = self.model.index(itemP.row(), 1, itemP.index().parent())
        itemS = self.model.itemFromIndex(idxS)
        return itemP, itemS

    def onPinFinished(self, path):
        ePin, ePinS = self.findPinItems(path)
        if ePinS:
            ePinS.setText('Finished')

    def onPinStatusChanged(self, path, status):
        nodesProcessed = status.get('Progress', None)
        ePin, ePinS = self.findPinItems(path)

        if not ePin:
            itemP = UneditableItem(path)
            itemS = UneditableItem(str(nodesProcessed) or iUnknown())
            self.model.invisibleRootItem().appendRow(
                    [itemP, itemS])
        else:
            if nodesProcessed:
                ePinS.setText(str(nodesProcessed))

class MainWindow(QMainWindow):
    tabnFManager = 'File Manager'
    tabnKeys = 'IPFS keys'
    tabnPinning = 'Pinning Status'
    tabnMediaPlayer = 'Media Player'

    def __init__(self, app):
        super(MainWindow, self).__init__()

        self.app = app

        self.ui = ui_galacteek.Ui_GalacteekWindow()
        self.ui.setupUi(self)

        self.ui.actionQuit.triggered.connect(self.quit)

        self.ui.actionCloseAllTabs.triggered.connect(
                self.onCloseAllTabs)
        self.ui.actionAboutGalacteek.triggered.connect(
                self.onAboutGalacteek)
        self.ui.actionShowPeersInformation.triggered.connect(
                self.onShowPeersInformation)
        self.ui.actionShowIpfsRefs.triggered.connect(
                self.onShowIpfsRefs)
        self.ui.actionSettings.triggered.connect(
                self.onSettings)

        self.menuManual = QMenu(iManual())
        self.ui.menuAbout.addMenu(self.menuManual)

        self.ui.myFilesButton.clicked.connect(self.onFileManagerClicked)
        self.ui.myFilesButton.setShortcut(QKeySequence('Ctrl+f'))
        self.ui.manageKeysButton.clicked.connect(self.onIpfsKeysClicked)
        self.ui.openBrowserTabButton.clicked.connect(self.onOpenBrowserTabClicked)
        self.ui.bookmarksButton.clicked.connect(self.addBookmarksTab)
        self.ui.bookmarksButton.setShortcut(QKeySequence('Ctrl+m'))
        self.ui.writeNewDocumentButton.clicked.connect(self.onWriteNewDocumentClicked)
        self.ui.mediaPlayerButton.clicked.connect(self.onOpenMediaPlayer)

        self.multiLoaderMenu = QMenu()
        self.multiLoaderHMenu = QMenu(iClipboardHistory())
        self.multiLoadHashAction = QAction(getIconIpfsIce(),
                iClipboardEmpty(), self,
                shortcut=QKeySequence('Ctrl+o'),
                triggered=self.onLoadFromClipboard)
        self.multiExploreHashAction = QAction(getIconIpfsIce(),
                iClipboardEmpty(), self,
                shortcut=QKeySequence('Ctrl+e'),
                triggered=self.onExploreFromClipboard)
        self.multiExploreHashAction.setEnabled(False)
        self.multiLoadHashAction.setEnabled(False)
        self.multiLoaderMenu.addAction(self.multiLoadHashAction)
        self.multiLoaderMenu.addAction(self.multiExploreHashAction)
        self.multiLoaderMenu.addMenu(self.multiLoaderHMenu)

        self.ui.clipboardMultiLoader.clicked.connect(self.onLoadFromClipboard)
        self.ui.clipboardMultiLoader.setMenu(self.multiLoaderMenu)
        self.ui.clipboardMultiLoader.setToolTip(iClipboardEmpty())
        self.ui.clipboardMultiLoader.setPopupMode(QToolButton.MenuButtonPopup)

        # Global pin-all button
        self.ui.pinAllGlobalButton.setCheckable(True)
        self.ui.pinAllGlobalButton.setAutoRaise(True)
        self.pinAllGlobalChecked = False
        self.ui.pinAllGlobalButton.toggled.connect(self.onToggledPinAllGlobal)

        self.ui.tabWidget.setTabsClosable(True)
        self.ui.tabWidget.tabCloseRequested.connect(self.onTabCloseRequest)
        self.ui.tabWidget.setElideMode(Qt.ElideMiddle)
        self.ui.tabWidget.setUsesScrollButtons(True)

        self.webProfile = QtWebEngineWidgets.QWebEngineProfile.defaultProfile()

        self.ui.menuUser_Profile.addSeparator()
        self.ui.menuUser_Profile.triggered.connect(self.onUserProfile)
        self.profilesActionGroup = QActionGroup(self)

        # Status bar setup
        self.ui.pinningStatusButton = QPushButton()
        self.ui.pinningStatusButton.setToolTip(iNoStatus())
        self.ui.pinningStatusButton.setIcon(getIcon('pin-black.png'))
        self.ui.pinningStatusButton.clicked.connect(self.onPinningStatusDetails)
        self.ui.pubsubStatusButton = QPushButton()
        self.ui.pubsubStatusButton.setIcon(getIcon('network-offline.png'))

        self.ui.statusbar.addPermanentWidget(self.ui.pinningStatusButton)
        self.ui.statusbar.addPermanentWidget(self.ui.pubsubStatusButton)
        self.ui.statusbar.setStyleSheet('background-color: #4a9ea1')

        # Connection status timer
        self.timerStatus = QTimer(self)
        self.timerStatus.timeout.connect(self.onMainTimerStatus)
        self.timerStatus.start(3000)

        self.enableButtons(False)

        # Connect ipfsctx signals
        self.app.ipfsCtx.ipfsRepositoryReady.connect(self.onRepoReady)
        self.app.ipfsCtx.pubsubMessageRx.connect(self.onPubsubRx)
        self.app.ipfsCtx.pubsubMessageTx.connect(self.onPubsubTx)
        self.app.ipfsCtx.profilesAvailable.connect(self.onProfilesList)
        self.app.ipfsCtx.profileChanged.connect(self.onProfileChanged)

        # App signals
        self.app.clipTracker.clipboardHasIpfs.connect(self.onClipboardIpfs)
        self.app.clipTracker.clipboardHistoryChanged.connect(self.onClipboardHistory)
        self.app.manualAvailable.connect(self.onManualAvailable)

        self.app.ipfsCtx.pinItemStatusChanged.connect(self.onPinStatusChanged)
        self.app.ipfsCtx.pinItemsCount.connect(self.onPinItemsCount)

        self.allTabs = []

        self.ui.tabWidget.removeTab(0)

    def getApp(self):
        return self.app

    def onProfileChanged(self, pName):
        for action in self.profilesActionGroup.actions():
            if action.data() == pName:
                action.setChecked(True)
                # Refresh the file manager
                tab = self.findTabFileManager()
                if tab:
                    tab.setupModel()
                    tab.pathSelectorDefault()

    def onUserProfile(self, action):
        if action is self.ui.actionNew_Profile:
            inText = QInputDialog.getText(self, iNewProfile(),
                    iNewProfile())
            profile, create = inText
            if create is True and profile:
                self.app.task(self.app.ipfsCtx.profileNew, profile)
        else:
            pName = action.text()
            if action.isChecked() and \
                    self.app.ipfsCtx.currentProfile.name != pName:
                rCode = self.app.ipfsCtx.profileChange(pName)

    def onProfilesList(self, pList):
        currentList = [action.data() for action in \
                self.profilesActionGroup.actions()]

        currentProfile = self.app.ipfsCtx.currentProfile

        for pName in pList:
            if pName in currentList:
                continue

            action = QAction(self.profilesActionGroup,
                    checkable=True, text=pName)
            action.setData(pName)

        for action in self.profilesActionGroup.actions():
            self.ui.menuUser_Profile.addAction(action)

    def onRepoReady(self):
        self.enableButtons()

    def onPubsubRx(self):
        now = QDateTime.currentDateTime()
        self.ui.pubsubStatusButton.setIcon(getIcon('network-transmit.png'))
        self.ui.pubsubStatusButton.setToolTip(
                'Pubsub: last message received {}'.format(now.toString()))

    def onPubsubTx(self):
        pass

    def onPinningStatusDetails(self):
        name = self.tabnPinning
        ft = self.findTabWithName(name)
        if ft:
            return self.ui.tabWidget.setCurrentWidget(ft)
        detailsTab = PinStatusDetails(self)
        self.registerTab(detailsTab, name)

    def updatePinningStatus(self):
        iconLoading = getIcon('pin-blue-loading.png')
        iconNormal = getIcon('pin-black.png')

        status = copy.copy(self.app.pinner.status())
        statusMsg = iItemsInPinningQueue(len(status))

        for pinPath, pinStatus in status.items():
            pinProgress = 'unknown'
            if pinStatus:
                pinProgress = pinStatus.get('Progress', 'unknown')

            statusMsg += iPinningItemStatus(pinPath, pinProgress)

        self.ui.pinningStatusButton.setToolTip(statusMsg)
        self.ui.pinningStatusButton.setStatusTip(statusMsg)

        del status

    def onPinItemsCount(self, count):
        iconLoading = getIcon('pin-blue-loading.png')
        iconNormal = getIcon('pin-black.png')

        if count > 0:
            self.ui.pinningStatusButton.setIcon(iconLoading)
        else:
            self.ui.pinningStatusButton.setIcon(iconNormal)

        self.updatePinningStatus()

    def onPinFinished(self, path):
        self.app.systemTrayMessage('PIN', iPinSuccess(path))

    def onPinStatusChanged(self, path, status):
        self.updatePinningStatus()

    def onManualAvailable(self, lang, entry):
        self.menuManual.addAction(lang, lambda:
            self.onOpenManual(lang, entry))

    def onOpenManual(self, lang, docEntry):
        self.addBrowserTab().browseIpfsHash(docEntry['Hash'])

    def enableButtons(self, flag=True):
        for btn in [ self.ui.myFilesButton,
                self.ui.manageKeysButton,
                self.ui.openBrowserTabButton,
                self.ui.bookmarksButton,
                self.ui.writeNewDocumentButton ]:
            btn.setEnabled(flag)

    def statusMessage(self, msg):
        self.ui.statusbar.showMessage(msg)

    def registerTab(self, tab, name, icon=None, current=False, add=True):
        if add is True:
            if icon:
                self.ui.tabWidget.addTab(tab, icon, name)
            else:
                self.ui.tabWidget.addTab(tab, name)

        self.allTabs.append(tab)

        if current is True:
            self.ui.tabWidget.setCurrentWidget(tab)

    def findTabFileManager(self):
        return self.findTabWithName(self.tabnFManager)

    def findTabIndex(self, w):
        return self.ui.tabWidget.indexOf(w)

    def findTabWithName(self, name):
        for idx in range(0, self.ui.tabWidget.count()):
            tName = self.ui.tabWidget.tabText(idx)

            if tName == name:
                return self.ui.tabWidget.widget(idx)

    def removeTabFromWidget(self, w):
        idx = self.ui.tabWidget.indexOf(w)
        if idx:
            self.ui.tabWidget.removeTab(idx)

    def onSettings(self):
        runDialog(settings.SettingsDialog, self.app)

    def onCloseAllTabs(self):
        self.ui.tabWidget.clear()

    def onToggledPinAllGlobal(self, checked):
        self.pinAllGlobalChecked = checked

    def onClipboardHistory(self, history):
        # Called when the clipboard history has changed
        self.multiLoaderHMenu.clear()
        hItems = history.items()

        def onHistoryItem(hItem):
            self.addBrowserTab().browseFsPath(hItem['path'])

        for hTs, hItem in hItems:
            self.multiLoaderHMenu.addAction(getIconIpfsIce(),
                    '{0} ({1})'.format(hItem['path'],
                        hItem['date'].toString()),
                    lambda: onHistoryItem(hItem))

    def onClipboardIpfs(self, valid, cid, path):
        self.multiExploreHashAction.setEnabled(valid)
        self.multiLoadHashAction.setEnabled(valid)
        if valid:
            self.multiExploreHashAction.setText(iClipLoaderExplore(path))
            self.multiLoadHashAction.setText(iClipLoaderBrowse(path))
            self.ui.clipboardMultiLoader.setToolTip(iFromClipboard(path))
        else:
            self.multiExploreHashAction.setText(iClipboardEmpty())
            self.multiLoadHashAction.setText(iClipboardEmpty())
            self.ui.clipboardMultiLoader.setToolTip(iClipboardEmpty())

    def onLoadFromClipboard(self):
        current = self.app.clipTracker.getCurrent()
        if current:
            self.addBrowserTab().browseFsPath(current['path'])
        else:
            messageBox(iClipboardEmpty())

    def onExploreFromClipboard(self):
        current = self.app.clipTracker.getCurrent()
        if current:
            self.app.task(self.exploreClipboardPath, current['path'])
        else:
            messageBox(iClipboardEmpty())

    @ipfsStatOp
    async def exploreClipboardPath(self, ipfsop, path, stat):
        if stat:
            view = ipfsview.IPFSHashViewToolBox(self, stat['Hash'])
            self.registerTab(view, stat['Hash'], current=True)

    def onAboutGalacteek(self):
        from galacteek import __version__
        QMessageBox.about(self, 'About Galacteek', iAbout())

    def onShowPeersInformation(self):
        pass

    def onShowIpfsRefs(self):
        pass

    def onMainTimerStatus(self):
        async def connectionInfo(oper):
            try:
                info = await oper.client.core.id()
            except:
                return self.statusMessage(iErrNoCx())

            nodeId = info.get('ID', iUnknown())
            nodeAgent = info.get('AgentVersion', iUnknownAgent())

            # Get IPFS peers list
            peers = await oper.peersList()
            if not peers:
                return self.statusMessage(iCxButNoPeers(
                    nodeId, nodeAgent))

            peersCount = len(peers)
            message = iConnectStatus(nodeId, nodeAgent, peersCount)
            self.statusMessage(message)

        self.app.ipfsTaskOp(connectionInfo)

    def keyPressEvent(self, event):
        # Ultimately this will be moved to configurable shortcuts
        modifiers = event.modifiers()

        if modifiers & Qt.ControlModifier:
            if event.key() == Qt.Key_T:
                self.addBrowserTab()
            if event.key() == Qt.Key_W:
                idx = self.ui.tabWidget.currentIndex()
                self.onTabCloseRequest(idx)

        super(MainWindow, self).keyPressEvent(event)

    def addMediaPlayerTab(self):
        name = self.tabnMediaPlayer
        ft = self.findTabWithName(name)
        if ft:
            return ft
        tab = mediaplayer.MediaPlayerTab(self)
        self.registerTab(tab, name, icon=getIcon('multimedia.png'),
                current=True)
        return tab

    def mediaPlayerQueue(self, path, mediaName=None):
        tab = self.addMediaPlayerTab()
        gwUrl = self.app.gatewayUrl
        mediaUrl = QUrl('{0}{1}'.format(gwUrl, path))
        tab.playFromUrl(mediaUrl, mediaName=mediaName)

    def addBookmarksTab(self):
        name = iHashmarks()
        ft = self.findTabWithName(name)
        if ft:
            return self.ui.tabWidget.setCurrentWidget(ft)

        tab = bookmarks.BookmarksTab(self)
        self.registerTab(tab, name, current=True)

    def onTabCloseRequest(self, idx):
        tabName = self.ui.tabWidget.tabText(idx)
        tab = self.ui.tabWidget.widget(idx)

        if not tab in self.allTabs:
            return False

        if tab.onClose() is True:
            self.ui.tabWidget.removeTab(idx)
            del tab

    def onOpenMediaPlayer(self):
        self.addMediaPlayerTab()

    def onOpenBrowserTabClicked(self):
        self.addBrowserTab()

    def onWriteNewDocumentClicked(self):
        w = textedit.AddDocumentWidget(self, parent=self.ui.tabWidget)
        self.registerTab(w, 'New document', current=True)

    def onFileManagerClicked(self):
        name = self.tabnFManager

        icon = getIcon('folder-open.png')
        ft = self.findTabWithName(name)
        if ft:
            ft.updateTree()
            return self.ui.tabWidget.setCurrentWidget(ft)

        filesTab = files.FilesTab(self, parent=self.ui.tabWidget)
        self.registerTab(filesTab, name, current=True, icon=icon)

        filesTab.updateTree()

    def onIpfsKeysClicked(self):
        name = self.tabnKeys
        ft = self.findTabWithName(name)
        if ft:
            return self.ui.tabWidget.setCurrentWidget(ft)

        keysTab = keys.KeysTab(self)
        self.registerTab(keysTab, name, current=True)

    def addBrowserTab(self, label='No page loaded'):
        icon = getIconIpfsIce()
        tab = browser.BrowserTab(self, parent=self.ui.tabWidget)
        self.ui.tabWidget.addTab(tab, icon, label)
        self.ui.tabWidget.setCurrentWidget(tab)

        mgr = self.app.settingsMgr
        if mgr.isTrue(CFG_SECTION_BROWSER, CFG_KEY_GOTOHOME):
            tab.loadHomePage()

        self.allTabs.append(tab)
        return tab

    def quit(self):
        # Qt and application exit
        self.app.onExit()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.app.systemTrayMessage('Galacteek', iMinimized())
