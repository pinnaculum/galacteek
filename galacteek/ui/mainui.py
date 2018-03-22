
import sys
import time
import os.path

from PyQt5.QtWidgets import (QApplication, QMainWindow,
        QDialog, QLabel, QTextEdit, QPushButton, QVBoxLayout,
        QSystemTrayIcon)
from PyQt5.QtCore import QCoreApplication, QUrl, QBuffer, QIODevice, Qt, QTimer
from PyQt5 import QtWebEngineWidgets, QtWebEngine, QtWebEngineCore
from PyQt5.QtGui import QClipboard, QPixmap, QIcon

from . import ui_galacteek
from . import browser, files, keys, settings, bookmarks
from .helpers import *
from ..appsettings import *
from .i18n import *

def iBookmarks():
    return QCoreApplication.translate('GalacteekWindow', 'Bookmarks')
def iMyFiles():
    return QCoreApplication.translate('GalacteekWindow', 'My Files')
def iKeys():
    return QCoreApplication.translate('GalacteekWindow', 'IPFS Keys')

class MainWindow(QMainWindow):
    tabnMyFiles = 'My Files'
    tabnKeys = 'IPFS keys'

    def __init__(self, app):
        super(MainWindow, self).__init__()

        self.app = app

        self.ui = ui_galacteek.Ui_GalacteekWindow()
        self.ui.setupUi(self)

        self.ui.actionQuit.triggered.connect(self.quit)
        self.ui.actionShowPeersInformation.triggered.connect(
                self.onShowPeersInformation)
        self.ui.actionShowIpfsRefs.triggered.connect(
                self.onShowIpfsRefs)
        self.ui.actionSettings.triggered.connect(
                self.onSettings)

        self.ui.myFilesButton.clicked.connect(self.onMyFilesClicked)
        self.ui.manageKeysButton.clicked.connect(self.onMyKeysClicked)
        self.ui.openBrowserTabButton.clicked.connect(self.onOpenBrowserTabClicked)
        self.ui.bookmarksButton.clicked.connect(self.addBookmarksTab)

        self.ui.tabWidget.setTabsClosable(True)
        self.ui.tabWidget.tabCloseRequested.connect(self.onTabCloseRequest)

        self.webProfile = QtWebEngineWidgets.QWebEngineProfile.defaultProfile()

        # Status bar setup
        self.ui.pinningStatusButton = QPushButton()
        self.ui.pinningStatusButton.setToolTip(iNoStatus())
        self.ui.pinningStatusButton.setIcon(getIcon('pin-black.png'))
        self.ui.statusbar.addPermanentWidget(self.ui.pinningStatusButton)
        self.ui.statusbar.setStyleSheet("background-color: #4a9ea1")

        # Main timer
        self.timerStatus = QTimer(self)
        self.timerStatus.timeout.connect(self.onMainTimerStatus)
        self.timerStatus.start(5000)

        self.allTabs = []
        self.ui.tabWidget.removeTab(0)

    def getApp(self):
        return self.app

    def statusMessage(self, msg):
        self.ui.statusbar.showMessage(msg)

    def registerTab(self, tab, name, current=False):
        self.ui.tabWidget.addTab(tab, name)
        self.allTabs.append(tab)

        if current is True:
            self.ui.tabWidget.setCurrentWidget(tab)

    def findTabMyFiles(self):
        return self.findTabWithName(self.tabnMyFiles)

    def findTabWithName(self, name):
        for idx in range(0, self.ui.tabWidget.count()):
            tname = self.ui.tabWidget.tabText(idx)
            tab = self.ui.tabWidget.widget(idx)
            if self.ui.tabWidget.tabText(idx) == name:
                return tab

    def onSettings(self):
        prefsDialog = settings.SettingsDialog(self.app)
        prefsDialog.exec_()
        prefsDialog.show()

    def onShowPeersInformation(self):
        pass

    def onShowIpfsRefs(self):
        pass

    def onMainTimerStatus(self):
        async def pinningUpdateStatus(client):
            iconLoading = getIcon('pin-blue-loading.png')
            iconNormal = getIcon('pin-black.png')
            pinner = self.app.pinner

            async with pinner.lock:
                status = pinner.status()
                statusMsg = iItemsInPinningQueue(len(status))
                self.ui.pinningStatusButton.setToolTip(statusMsg)
                self.ui.pinningStatusButton.setStatusTip(statusMsg)

                if len(status) > 0:
                    self.ui.pinningStatusButton.setIcon(iconLoading)
                else:
                    self.ui.pinningStatusButton.setIcon(iconNormal)

        async def connectionInfo(oper):
            try:
                info = await oper.client.core.id()
            except:
                return self.statusMessage(iErrNoCx())

            nodeId = info.get('ID', iUnknown())
            nodeAgent = info.get('AgentVersion', iUnknownAgent())

            # Get IPFS swarm status
            peers = await oper.peersList()
            if not peers:
                return self.statusMessage(iErrNoPeers())

            peersCount = len(peers)
            message = iConnectStatus(nodeId, nodeAgent, peersCount)
            self.statusMessage(message)

        self.app.ipfsTaskOp(connectionInfo)
        self.app.ipfsTask(pinningUpdateStatus)

    def keyPressEvent(self, event):
        modifiers = event.modifiers()

        if modifiers & Qt.ControlModifier:
            if event.key() == Qt.Key_N:
                self.addBrowserTab()
            if event.key() == Qt.Key_T:
                self.addBrowserTab()
            if event.key() == Qt.Key_M:
                self.addBookmarksTab()
            if event.key() == Qt.Key_W:
                idx = self.ui.tabWidget.currentIndex()
                #w = self.ui.tabWidget.currentWidget()
                self.onTabCloseRequest(idx)

                #self.ui.tabWidget.removeTab(idx)
                #del w

        if event.key() == Qt.Key_F1:
            self.addBookmarksTab()

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

        if tabName == self.tabnMyFiles:
            self.ui.tabWidget.removeTab(idx)
            return False

        if hasattr(tab, 'onClose'):
            tab.onClose()

        self.ui.tabWidget.removeTab(idx)
        del tab

    def onOpenBrowserTabClicked(self):
        self.addBrowserTab()

    def onMyFilesClicked(self):
        name = self.tabnMyFiles

        icon = getIcon('folder-open.png')
        ft = self.findTabWithName(name)
        if ft:
            ft.updateTree()
            return self.ui.tabWidget.setCurrentWidget(ft)

        filesTab = files.FilesTab(self, parent=self.ui.tabWidget)
        self.registerTab(filesTab, name, current=True)

        filesTab.updateTree()

    def onMyKeysClicked(self):
        name = self.tabnKeys
        ft = self.findTabWithName(name)
        if ft:
            return self.ui.tabWidget.setCurrentWidget(ft)

        keysTab = keys.KeysTab(self, parent=self.ui.tabWidget)
        self.registerTab(keysTab, name, current=True)

    def addBrowserTab(self, label='No page loaded'):
        icon = getIcon('ipfs-logo-128-ice.png')
        tab = browser.BrowserTab(self, parent=self.ui.tabWidget)
        self.ui.tabWidget.addTab(tab, icon, label)
        self.ui.tabWidget.setCurrentWidget(tab)

        mgr = self.getApp().settingsMgr
        if mgr.isTrue(CFG_SECTION_BROWSER, CFG_KEY_GOTOHOME):
            home = mgr.eGet(S_HOMEURL)
            tab.enterUrl(QUrl(home))

        self.allTabs.append(tab)
        return tab

    def quit(self):
        # Qt and application exit
        self.app.onExit()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.getApp().systemTrayMessage('Galacteek', iMinimized())
