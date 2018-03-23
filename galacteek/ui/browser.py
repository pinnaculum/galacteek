
import sys
import time
import os.path
import re

from PyQt5.QtWidgets import (QWidget, QFrame, QApplication, QMainWindow,
        QDialog, QLabel, QPushButton, QVBoxLayout, QAction,
        QMenu, QTabWidget, QInputDialog, QMessageBox)

from PyQt5.QtPrintSupport import *

from PyQt5.QtCore import QUrl, QBuffer, QIODevice, Qt, QCoreApplication, QObject
from PyQt5 import QtWebEngineWidgets, QtWebEngine, QtWebEngineCore
from PyQt5.Qt import QByteArray
from PyQt5.QtGui import QClipboard, QPixmap, QIcon

from yarl import URL
import cid

from . import ui_browsertab
from . import galacteek_rc
from .helpers import *

SCHEME_DWEB = 'dweb'
SCHEME_FS = 'fs'

# i18n
def iOpenInTab():
    return QCoreApplication.translate('BrowserTabForm', 'Open link in tab')
def iDownload():
    return QCoreApplication.translate('BrowserTabForm', 'Download')
def iPin():
    return QCoreApplication.translate('BrowserTabForm', 'PIN')
def iPinThisPage():
    return QCoreApplication.translate('BrowserTabForm', 'PIN (this page)')
def iPinRecursive():
    return QCoreApplication.translate('BrowserTabForm', 'PIN (recursive)')
def iEnterIpfsHash():
    return QCoreApplication.translate('BrowserTabForm', 'Enter an IPFS multihash')
def iEnterIpnsHash():
    return QCoreApplication.translate('BrowserTabForm',
        'Enter an IPNS multihash/name')
def iPinSuccess(path):
    return QCoreApplication.translate('BrowserTabForm',
        '{0} was pinned successfully').format(path)

def iBookmarked(path):
    return QCoreApplication.translate('BrowserTabForm',
        'Bookmarked {0}').format(path)

class IPFSSchemeHandler(QtWebEngineCore.QWebEngineUrlSchemeHandler):
    def __init__(self, engine, browsertab, parent = None):
        self.webengine = engine
        self.browsertab = browsertab
        QtWebEngineCore.QWebEngineUrlSchemeHandler.__init__(self, parent)

    def requestStarted(self, request):
        method = request.requestMethod()
        url = request.requestUrl()
        scheme = url.scheme()
        host = url.host()
        path = url.path()
        gatewayUrl = self.browsertab.gatewayUrl

        def redirectIpfs():
            yUrl = URL(url.toString())
            if len(yUrl.parts) < 3:
                return None

            newurl = QUrl("{0}/{1}".format(gatewayUrl, url.path()))
            return request.redirect(newurl)

        def redirectIpns():
            yUrl = URL(url.toString())
            if len(yUrl.parts) < 3:
                return
            newurl = QUrl("{0}/{1}".format(gatewayUrl, url.path()))
            return request.redirect(newurl)

        if scheme == SCHEME_FS or scheme == SCHEME_DWEB:
            # Handle fs:/{ipfs,ipns}/path and dweb:/{ipfs,ipns}/path

            if path.startswith("/ipfs/"):
                return redirectIpfs()
            if path.startswith("/ipns/"):
                return redirectIpns()

            # This would handle fs://{ipfs,ipns}/ but really we shouldn't care
            if host == 'ipfs':
                return redirectIpfs()
            if host == 'ipns':
                return redirectIpns()

class WebView(QtWebEngineWidgets.QWebEngineView):
    def __init__(self, browsertab, parent = None):
        super(QtWebEngineWidgets.QWebEngineView, self).__init__(parent = parent)

        self.browsertab = browsertab
        schemeHandler = IPFSSchemeHandler(self, self.browsertab, parent = self)
        profile = self.page().profile()

        # Register our naughty scheme handlers
        profile.installUrlSchemeHandler(QByteArray(b'fs'), schemeHandler)
        profile.installUrlSchemeHandler(QByteArray(b'dweb'), schemeHandler)

    def contextMenuEvent(self, event):
        currentPage = self.page()
        contextMenuData = currentPage.contextMenuData()
        menu = self.page().createStandardContextMenu()
        actions = menu.actions()
        menu.addSeparator()

        act1 = menu.addAction(iOpenInTab(), lambda:
                self.openInTab(contextMenuData))
        act1 = menu.addAction(iDownload(), lambda:
                self.downloadLink(contextMenuData))
        ipfsMenu = QMenu('IPFS')
        ipfsMenu.setIcon(getIcon('ipfs-logo-128-black.png'))
        menu.addMenu(ipfsMenu)
        act = ipfsMenu.addAction(getIcon('pin.png'), iPin(), lambda:
                self.pinPage(contextMenuData))

        menu.exec(event.globalPos())

    def pinPage(self, menudata):
        url = menudata.linkUrl()
        path = url.path()
        self.browsertab.pinPath(path, recursive=False)

    def openInTab(self, menudata):
        url = menudata.linkUrl()
        tab = self.browsertab.mainWindow.addBrowserTab()
        tab.enterUrl(url)

    def downloadLink(self, menudata):
        url = menudata.linkUrl()
        self.page().download(url, None)

    def createWindow(self, wtype):
        pass

class BrowserKeyFilter(QObject):
    ctrlbPressed = pyqtSignal()

    def eventFilter(self,  obj,  event):
        if event.type() == QEvent.KeyPress:
            modifiers = event.modifiers()

            key = event.key()
            if modifiers & Qt.ControlModifier:
                if key == Qt.Key_B:
                    self.ctrlbPressed.emit()
                    return True
        return False

class BrowserTab(QWidget):
    def __init__(self, mainWindow, parent = None):
        super(QWidget, self).__init__(parent = parent)

        self.mainWindow = mainWindow
        self.app = self.mainWindow.getApp()

        self.ui = ui_browsertab.Ui_BrowserTabForm()
        self.ui.setupUi(self)

        self.ui.webEngineView = WebView(self)
        self.webProfile = QtWebEngineWidgets.QWebEngineProfile.defaultProfile()

        self.ui.vLayoutBrowser.addWidget(self.ui.webEngineView)

        self.ui.webEngineView.urlChanged.connect(self.onUrlChanged)
        self.ui.webEngineView.loadFinished.connect(self.onLoadFinished)
        self.ui.webEngineView.iconChanged.connect(self.onIconChanged)
        self.ui.webEngineView.loadProgress.connect(self.onLoadProgress)

        self.ui.urlZone.returnPressed.connect(self.onUrlEdit)
        self.ui.backButton.clicked.connect(self.backButtonClicked)
        self.ui.forwardButton.clicked.connect(self.forwardButtonClicked)
        self.ui.refreshButton.clicked.connect(self.refreshButtonClicked)
        self.ui.loadFromClipboardButton.clicked.connect(self.loadFromClipboardButtonClicked)
        self.ui.loadIpfsHashButton.clicked.connect(self.loadIpfsHashButtonClicked)
        self.ui.loadIpnsHashButton.clicked.connect(self.loadIpnsHashButtonClicked)
        #self.ui.printButton.clicked.connect(self.printButtonClicked)

        # Prepare the pin combo box
        iconPin = getIcon('pin.png')
        self.ui.pinComboBox.insertItem(0, iPinThisPage())
        self.ui.pinComboBox.setItemIcon(0, iconPin)
        self.ui.pinComboBox.insertItem(1, iPinRecursive())
        self.ui.pinComboBox.setItemIcon(1, iconPin)
        self.ui.pinComboBox.activated.connect(self.pinComboClicked)

        # Event filter
        evfilter = BrowserKeyFilter(self)
        evfilter.ctrlbPressed.connect(self.onBookmarkPage)
        self.installEventFilter(evfilter)

        self.currentUrl = None
        self.currentIpfsResource = None

    @property
    def currentPageTitle(self):
        return self.ui.webEngineView.page().title()

    @property
    def gatewayAuthority(self):
        params = self.app.ipfsConnParams
        return '{0}:{1}'.format(params.getHost(), params.getGatewayPort())

    @property
    def gatewayUrl(self):
        params = self.app.ipfsConnParams
        return params.getGatewayUrl()

    def onBookmarkPage(self):
        if self.currentIpfsResource:
            self.app.bookmarks.add(self.currentIpfsResource,
                    self.currentPageTitle)
            messageBox(iBookmarked(self.currentIpfsResource))

    def onPinSuccess(self, f):
        return self.app.systemTrayMessage('PIN', iPinSuccess(f.result()))

    def onPinSuccessMbox(self, f):
        msgBox = QMessageBox()
        msgBox.setText(iPinSuccess(f.result()))
        msgBox.show()
        return msgBox.exec_()

    def pinPath(self, path, recursive=True):
        async def pinCoro(client, path):
            pinner = self.mainWindow.getApp().pinner
            await pinner.queue.put((path, recursive, self.onPinSuccess))

        self.mainWindow.getApp().ipfsTask(pinCoro,
                path)

    def printButtonClicked(self):
        printer = QPrinter()
        dialog = QPrintDialog(printer, self)
        dialog.setModal(True)

        def success(ok):
            return ok

        if dialog.exec_() == QDialog.Accepted:
            currentPage = self.ui.webEngineView.page()
            currentPage.print(printer, success)

    def pinPageButtonClicked(self):
        self.pinPath(self.currentIpfsResource, recursive=False)

    def pinComboClicked(self, idx):
        if not self.currentIpfsResource:
            return
        if idx == 0:
            self.pinPath(self.currentIpfsResource, recursive=False)
        if idx == 1:
            self.pinPath(self.currentIpfsResource, recursive=True)

    def loadFromClipboardButtonClicked(self):
        app = self.mainWindow.getApp()
        clipboardSelection = app.clipboard().text(QClipboard.Selection)
        self.browseIpfsHash(clipboardSelection)

    def loadIpfsHashButtonClicked(self):
        text, ok = QInputDialog.getText(self, 'Load IPFS multihash dialog',
                iEnterIpfsHash())
        if ok:
            self.browseIpfsHash(text)

    def loadIpnsHashButtonClicked(self):
        text, ok = QInputDialog.getText(self, 'Load IPNS multihash/name dialog',
                iEnterIpnsHash())
        if ok:
            self.browseIpnsHash(text)

    def refreshButtonClicked(self):
        self.ui.webEngineView.reload()

    def backButtonClicked(self):
        currentPage = self.ui.webEngineView.page()
        currentPage.history().back()

    def forwardButtonClicked(self):
        currentPage = self.ui.webEngineView.page()
        currentPage.history().forward()

    def historyButtonClicked(self):
        pass

    def onUrlChanged(self, url):
        if url.authority() == self.gatewayAuthority:
            self.currentIpfsResource = url.path()
            self.ui.urlZone.clear()
            # Content loaded from IPFS gateway, this is IPFS content
            self.ui.urlZone.insert('fs:{}'.format(url.path()))
        else:
            self.ui.urlZone.clear()
            self.ui.urlZone.insert(url.toString())

    def onLoadFinished(self, ok):
        currentPageTitle = self.ui.webEngineView.page().title()
        if currentPageTitle.startswith(self.gatewayAuthority):
            currentPageTitle = 'No title'

        idx = self.mainWindow.ui.tabWidget.indexOf(self)
        self.mainWindow.ui.tabWidget.setTabText(idx, currentPageTitle)

    def onIconChanged(self, icon):
        pass

    def onLoadProgress(self, progress):
        self.ui.progressBar.setValue(progress)

    def browseFsPath(self, path):
        self.enterUrl(QUrl('fs:{}'.format(path)))

    def browseIpfsHash(self, ipfshash):
        self.enterUrl(QUrl('fs:/ipfs/{}'.format(ipfshash)))

    def browseIpnsHash(self, ipnshash):
        self.enterUrl(QUrl('fs:/ipns/{}'.format(ipnshash)))

    def enterUrl(self, url):
        self.ui.urlZone.clear()
        self.ui.urlZone.insert(url.toString())
        self.ui.webEngineView.load(url)

    def onUrlEdit(self):
        inputStr = self.ui.urlZone.text().strip()
        self.enterUrl(QUrl(inputStr))
