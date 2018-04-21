
import sys
import time
import os.path
import copy

from PyQt5.QtWidgets import (QApplication, QMainWindow,
        QDialog, QLabel, QTextEdit, QPushButton, QVBoxLayout,
        QSystemTrayIcon)
from PyQt5.QtCore import (QCoreApplication, QUrl, QBuffer, QIODevice, Qt,
    QTimer, QFile)
from PyQt5.QtCore import pyqtSignal, QUrl, QObject, QDateTime
from PyQt5 import QtWebEngineWidgets, QtWebEngine, QtWebEngineCore
from PyQt5.QtGui import QClipboard, QPixmap, QIcon, QKeySequence

from galacteek.ipfs.ipfsops import *
from . import ui_galacteek
from . import browser, files, keys, settings, bookmarks, textedit
from .helpers import *
from .dialogs import *
from ..appsettings import *
from .i18n import *

def iBookmarks():
    return QCoreApplication.translate('GalacteekWindow', 'Bookmarks')
def iMyFiles():
    return QCoreApplication.translate('GalacteekWindow', 'My Files')
def iKeys():
    return QCoreApplication.translate('GalacteekWindow', 'IPFS Keys')

def iAbout():
    from galacteek import __version__
    return QCoreApplication.translate('GalacteekWindow', '''
        <p><b>Galacteek</b> is a simple IPFS browser and content publisher
        </p>
        <p>Author: David Ferlier</p>
        <p>Galacteek version {0}</p>''').format(__version__)

class MainWindow(QMainWindow):
    tabnMyFiles = 'My Files'
    tabnKeys = 'IPFS keys'

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

        self.ui.myFilesButton.clicked.connect(self.onMyFilesClicked)
        self.ui.myFilesButton.setShortcut(QKeySequence('Ctrl+f'))
        self.ui.manageKeysButton.clicked.connect(self.onIpfsKeysClicked)
        self.ui.openBrowserTabButton.clicked.connect(self.onOpenBrowserTabClicked)
        self.ui.bookmarksButton.clicked.connect(self.addBookmarksTab)
        self.ui.bookmarksButton.setShortcut(QKeySequence('Ctrl+m'))
        self.ui.writeNewDocumentButton.clicked.connect(self.onWriteNewDocumentClicked)

        # Global pin-all button
        self.ui.pinAllGlobalButton.setCheckable(True)
        self.ui.pinAllGlobalButton.setAutoRaise(True)
        self.pinAllGlobalChecked = False
        self.ui.pinAllGlobalButton.toggled.connect(self.onToggledPinAllGlobal)

        self.ui.tabWidget.setTabsClosable(True)
        self.ui.tabWidget.tabCloseRequested.connect(self.onTabCloseRequest)

        self.webProfile = QtWebEngineWidgets.QWebEngineProfile.defaultProfile()

        # Status bar setup
        self.ui.pinningStatusButton = QPushButton()
        self.ui.pinningStatusButton.setToolTip(iNoStatus())
        self.ui.pinningStatusButton.setIcon(getIcon('pin-black.png'))
        self.ui.pubsubStatusButton = QPushButton()
        self.ui.pubsubStatusButton.setIcon(getIcon('network-offline.png'))

        self.ui.statusbar.addPermanentWidget(self.ui.pinningStatusButton)
        self.ui.statusbar.addPermanentWidget(self.ui.pubsubStatusButton)
        self.ui.statusbar.setStyleSheet('background-color: #4a9ea1')

        # Connection status timer
        self.timerStatus = QTimer(self)
        self.timerStatus.timeout.connect(self.onMainTimerStatus)
        self.timerStatus.start(3000)

        # Connect ipfsctx signals
        self.app.ipfsCtx.ipfsRepositoryReady.connect(self.onRepoReady)
        self.app.ipfsCtx.pubsubMessageRx.connect(self.onPubsubRx)
        self.app.ipfsCtx.pubsubMessageTx.connect(self.onPubsubTx)

        self.app.ipfsCtx.pinItemStatusChanged.connect(self.onPinStatusChanged)
        self.app.ipfsCtx.pinItemsCount.connect(self.onPinItemsCount)

        self.allTabs = []

        self.ui.tabWidget.removeTab(0)

    def getApp(self):
        return self.app

    def onRepoReady(self):
        pass

    def onPubsubRx(self):
        now = QDateTime.currentDateTime()
        self.ui.pubsubStatusButton.setIcon(getIcon('network-transmit.png'))
        self.ui.pubsubStatusButton.setToolTip(
                'Pubsub: last message received {}'.format(now.toString()))

    def onPubsubTx(self):
        pass

    def updatePinningStatus(self):
        iconLoading = getIcon('pin-blue-loading.png')
        iconNormal = getIcon('pin-black.png')

        status = copy.copy(self.app.pinner.status())
        statusMsg = iItemsInPinningQueue(len(status))

        for pinPath, pinStatus in status.items():
            pinProgress = 'unknown'
            if pinStatus:
                pinProgress = pinStatus.get('Progress', 'unknown')

            statusMsg += '\nPath: {0}, nodes processed: {1}'.format(
                pinPath, pinProgress)

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

    def findTabMyFiles(self):
        return self.findTabWithName(self.tabnMyFiles)

    def findTabIndex(self, w):
        return self.ui.tabWidget.indexOf(w)

    def findTabWithName(self, name):
        for idx in range(0, self.ui.tabWidget.count()):
            tname = self.ui.tabWidget.tabText(idx)
            tab = self.ui.tabWidget.widget(idx)
            if self.ui.tabWidget.tabText(idx) == name:
                return tab

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

    def addMediaPlayerTab(self, hash):
        from galacteek.ui import mediaplayer
        tab = mediaplayer.MediaPlayerTab(self)
        gwUrl = self.app.gatewayUrl
        mediaUrl = QUrl('{0}/{1}'.format(gwUrl, joinIpfs(hash)))
        tab.playFromUrl(mediaUrl)
        self.registerTab(tab, hash, current=True)

    def addBookmarksTab(self):
        name = iBookmarks()
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

        if hasattr(tab, 'onClose'):
            tab.onClose()

        self.ui.tabWidget.removeTab(idx)
        del tab

    def onOpenBrowserTabClicked(self):
        self.addBrowserTab()

    def onWriteNewDocumentClicked(self):
        w = textedit.AddDocumentWidget(self, parent=self.ui.tabWidget)
        self.registerTab(w, 'New document', current=True)

    def onMyFilesClicked(self):
        name = self.tabnMyFiles

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
