
import sys
import time
import os.path
import re

from PyQt5.QtWidgets import (QWidget, QFrame, QApplication, QMainWindow,
        QDialog, QLabel, QPushButton, QVBoxLayout, QAction, QStyle,
        QMenu, QTabWidget, QInputDialog, QMessageBox, QToolButton, QFileDialog)

from PyQt5.QtPrintSupport import *

from PyQt5.QtCore import (QUrl, QIODevice, Qt, QCoreApplication, QObject,
    pyqtSignal, QMutex, QFile)
from PyQt5 import QtWebEngineWidgets, QtWebEngine, QtWebEngineCore
from PyQt5.QtWebEngineWidgets import (QWebEngineDownloadItem, QWebEngineScript,
        QWebEngineSettings)
from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor
from PyQt5.Qt import QByteArray
from PyQt5.QtGui import QClipboard, QPixmap, QIcon, QKeySequence

from yarl import URL

from galacteek import log
from galacteek.ipfs.wrappers import *

from . import ui_browsertab
from . import galacteek_rc
from .helpers import *
from .dialogs import *
from .hashmarks import *
from .i18n import *
from .widgets import *
from ..appsettings import *
from galacteek.ipfs import cidhelpers

SCHEME_DWEB = 'dweb'
SCHEME_FS = 'fs'
SCHEME_IPFS = 'ipfs'

# i18n
def iOpenInTab():
    return QCoreApplication.translate('BrowserTabForm', 'Open link in tab')
def iOpenWith():
    return QCoreApplication.translate('BrowserTabForm', 'Open with')
def iDownload():
    return QCoreApplication.translate('BrowserTabForm', 'Download')
def iPin():
    return QCoreApplication.translate('BrowserTabForm', 'PIN')
def iPinThisPage():
    return QCoreApplication.translate('BrowserTabForm', 'PIN (this page)')
def iPinRecursive():
    return QCoreApplication.translate('BrowserTabForm', 'PIN (recursive)')
def iFollow():
    return QCoreApplication.translate('BrowserTabForm',
        'Follow IPNS resource')

def iEnterIpfsCID():
    return QCoreApplication.translate('BrowserTabForm', 'Enter an IPFS CID')

def iBrowseHomePage():
    return QCoreApplication.translate('BrowserTabForm',
        'Go to home page')

def iBrowseIpfsCID():
    return QCoreApplication.translate('BrowserTabForm',
        'Browse IPFS resource (CID)')

def iBrowseIpfsMultipleCID():
    return QCoreApplication.translate('BrowserTabForm',
        'Browse multiple IPFS resources (CID)')

def iEnterIpfsCIDDialog():
    return QCoreApplication.translate('BrowserTabForm',
        'Load IPFS CID dialog')

def iFollowIpnsDialog():
    return QCoreApplication.translate('BrowserTabForm',
        'IPNS add feed dialog')

def iBrowseIpnsHash():
    return QCoreApplication.translate('BrowserTabForm',
        'Browse IPNS resource from hash/name')

def iEnterIpns():
    return QCoreApplication.translate('BrowserTabForm',
        'Enter an IPNS hash/name')

def iEnterIpnsDialog():
    return QCoreApplication.translate('BrowserTabForm',
        'Load IPNS key dialog')

def iHashmarked(path):
    return QCoreApplication.translate('BrowserTabForm',
        'Hashmarked {0}').format(path)

def iHashmarkTitleDialog():
    return QCoreApplication.translate('BrowserTabForm',
        'Hashmark title')

def iInvalidUrl(text):
    return QCoreApplication.translate('BrowserTabForm',
        'Invalid URL: {0}').format(text)

def iInvalidCID(text):
    return QCoreApplication.translate('BrowserTabForm',
        '{0} is an invalid IPFS CID (Content IDentifier)').format(text)

def fsPath(path):
    return '{0}:{1}'.format(SCHEME_IPFS, path)

def usesIpfsNs(url):
    return url.startswith('{0}:/'.format(SCHEME_IPFS))

class IPFSSchemeHandler(QtWebEngineCore.QWebEngineUrlSchemeHandler):
    def __init__(self, app, parent=None):
        QtWebEngineCore.QWebEngineUrlSchemeHandler.__init__(self, parent)
        self.app = app

    def requestStarted(self, request):
        url = request.requestUrl()
        scheme = url.scheme()
        path = url.path()

        log.debug('IPFS scheme handler request {url} {scheme} {path} {method}'.format(
            url=url.toString(), scheme=scheme, path=path,
            method=request.requestMethod()))

        def redirectIpfs(path):
            yUrl = URL(url.toString())

            if len(yUrl.parts) < 3:
                messageBox(iInvalidUrl())
                return None

            newUrl = self.app.subUrl(path)

            if url.hasFragment():
                newUrl.setFragment(url.fragment())
            if url.hasQuery():
                newUrl.setQuery(url.query())

            log.debug('IPFS scheme handler redirects to {redirect} {scheme} \
                    {valid}'.format(
                redirect=newUrl.toString(), scheme=newUrl.scheme(),
                valid=newUrl.isValid()))
            return request.redirect(newUrl)

        if scheme in [SCHEME_FS, SCHEME_IPFS, SCHEME_DWEB]:
            # Handle scheme:/{ipfs,ipns}/path

            if path.startswith('/ipfs/') or path.startswith('/ipns/'):
                return redirectIpfs(path)

class RequestInterceptor(QWebEngineUrlRequestInterceptor):
    def interceptRequest(self, info):
        url = info.requestUrl()

class WebView(QtWebEngineWidgets.QWebEngineView):
    def __init__(self, browserTab, enablePlugins=False, parent = None):
        super(QtWebEngineWidgets.QWebEngineView, self).__init__(parent = parent)

        self.mutex = QMutex()
        self.browserTab = browserTab

        self.webSettings = self.settings()
        self.webSettings.setAttribute(QWebEngineSettings.PluginsEnabled,
                enablePlugins)

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
        openWithMenu = QMenu(iOpenWith())
        openWithMenu.addAction('Media player', lambda:
                self.openWithMediaPlayer(contextMenuData))
        menu.addMenu(openWithMenu)

        menu.exec(event.globalPos())

    def openWithMediaPlayer(self, menudata):
        url = menudata.linkUrl()
        self.browserTab.gWindow.mediaPlayerQueue(url.path())

    def pinPage(self, menudata):
        url = menudata.linkUrl()
        path = url.path()
        self.browserTab.pinPath(path, recursive=False)

    def openInTab(self, menudata):
        url = menudata.linkUrl()
        tab = self.browserTab.gWindow.addBrowserTab()
        tab.enterUrl(url)

    def downloadLink(self, menudata):
        url = menudata.linkUrl()
        self.page().download(url, None)

    def createWindow(self, wtype):
        pass

class BrowserKeyFilter(QObject):
    hashmarkPressed = pyqtSignal()
    savePagePressed = pyqtSignal()

    def eventFilter(self,  obj,  event):
        if event.type() == QEvent.KeyPress:
            modifiers = event.modifiers()

            key = event.key()
            if modifiers & Qt.ControlModifier:
                if key == Qt.Key_B:
                    self.hashmarkPressed.emit()
                    return True
                if key == Qt.Key_S:
                    self.savePagePressed.emit()
                    return True
        return False

class BrowserTab(GalacteekTab):
    # signals
    ipfsPathVisited = pyqtSignal(str)

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

        self.ui = ui_browsertab.Ui_BrowserTabForm()
        self.ui.setupUi(self)

        # Install scheme handler early on
        self.webProfile = QtWebEngineWidgets.QWebEngineProfile.defaultProfile()
        self.installIpfsSchemeHandler()

        self.ui.webEngineView = WebView(self,
                enablePlugins=self.app.settingsMgr.ppApiPlugins)
        self.ui.vLayoutBrowser.addWidget(self.ui.webEngineView)

        self.webScripts = self.webProfile.scripts()
        self.installScripts()

        self.ui.webEngineView.urlChanged.connect(self.onUrlChanged)
        self.ui.webEngineView.loadFinished.connect(self.onLoadFinished)
        self.ui.webEngineView.iconChanged.connect(self.onIconChanged)
        self.ui.webEngineView.loadProgress.connect(self.onLoadProgress)

        self.ui.urlZone.returnPressed.connect(self.onUrlEdit)
        self.ui.backButton.clicked.connect(self.backButtonClicked)
        self.ui.backButton.setIcon(self.style().standardIcon(QStyle.SP_ArrowLeft))
        self.ui.forwardButton.clicked.connect(self.forwardButtonClicked)
        self.ui.forwardButton.setIcon(self.style().standardIcon(QStyle.SP_ArrowRight))
        self.ui.refreshButton.clicked.connect(self.refreshButtonClicked)
        self.ui.stopButton.clicked.connect(self.stopButtonClicked)
        self.ui.loadFromClipboardButton.clicked.connect(self.loadFromClipboardButtonClicked)
        self.ui.loadFromClipboardButton.setEnabled(self.app.clipTracker.hasIpfs)
        self.ui.hashmarkPageButton.clicked.connect(self.onHashmarkPage)

        # Setup the tool button for browsing IPFS content
        self.loadIpfsMenu = QMenu()
        self.loadIpfsCIDAction = QAction(getIconIpfsIce(),
                iBrowseIpfsCID(),self,
                shortcut=QKeySequence('Ctrl+l'),
                triggered=self.onLoadIpfsCID)
        self.loadIpfsMultipleCIDAction = QAction(getIconIpfsIce(),
                iBrowseIpfsMultipleCID(), self,
                triggered=self.onLoadIpfsMultipleCID)
        self.loadIpnsAction = QAction(getIconIpfsWhite(),
                iBrowseIpnsHash(),self,
                triggered=self.onLoadIpns)
        self.followIpnsAction = QAction(getIconIpfsWhite(),
                iFollow(),self,
                triggered=self.onFollowIpns)
        self.loadHomeAction = QAction(getIcon('go-home.png'),
                iBrowseHomePage(),self,
                triggered=self.onLoadHome)

        self.loadIpfsMenu.addAction(self.loadIpfsCIDAction)
        self.loadIpfsMenu.addAction(self.loadIpfsMultipleCIDAction)
        self.loadIpfsMenu.addAction(self.loadIpnsAction)
        self.loadIpfsMenu.addAction(self.followIpnsAction)
        self.loadIpfsMenu.addAction(self.loadHomeAction)

        self.ui.loadIpfsButton.setMenu(self.loadIpfsMenu)
        self.ui.loadIpfsButton.setPopupMode(QToolButton.MenuButtonPopup)
        self.ui.loadIpfsButton.clicked.connect(self.onLoadIpfsCID)

        self.ui.pinAllButton.setCheckable(True)
        self.ui.pinAllButton.setAutoRaise(True)
        self.ui.pinAllButton.setChecked(self.gWindow.pinAllGlobalChecked)
        self.ui.pinAllButton.toggled.connect(self.onToggledPinAll)

        # Prepare the pin combo box
        iconPin = getIcon('pin.png')
        self.ui.actionComboBox.insertItem(0, iPinThisPage())
        self.ui.actionComboBox.setItemIcon(0, iconPin)
        self.ui.actionComboBox.insertItem(1, iPinRecursive())
        self.ui.actionComboBox.setItemIcon(1, iconPin)
        self.ui.actionComboBox.activated.connect(self.actionComboClicked)

        # Event filter
        evfilter = BrowserKeyFilter(self)
        evfilter.hashmarkPressed.connect(self.onHashmarkPage)
        self.installEventFilter(evfilter)

        self.app.clipTracker.clipboardHasIpfs.connect(self.onClipboardIpfs)
        self.ipfsPathVisited.connect(self.onPathVisited)

        self.currentUrl = None
        self.currentIpfsResource = None
        self.currentPageTitle = None

    @property
    def webView(self):
        return self.ui.webEngineView

    @property
    def tabPage(self):
        return self.gWindow.ui.tabWidget.widget(self.tabPageIdx)

    @property
    def tabPageIdx(self):
        return self.gWindow.ui.tabWidget.indexOf(self)

    @property
    def gatewayAuthority(self):
        return self.app.gatewayAuthority

    @property
    def gatewayUrl(self):
        return self.app.gatewayUrl

    @property
    def pinAll(self):
        return self.ui.pinAllButton.isChecked()

    def installScripts(self):
        # Install the browserified js-ipfs API

        exSc = self.webScripts.findScript('js-ipfs-api')
        if self.app.settingsMgr.jsIpfsApi is True and exSc.isNull():
            jsFile = QFile(':/share/js/js-ipfs-api/index.js')
            if not jsFile.open(QFile.ReadOnly):
                return
            scriptJsIpfs = QWebEngineScript()
            scriptJsIpfs.setName('js-ipfs-api')
            scriptJsIpfs.setSourceCode(jsFile.readAll().data().decode('utf-8'))
            scriptJsIpfs.setWorldId(QWebEngineScript.MainWorld)
            scriptJsIpfs.setInjectionPoint(QWebEngineScript.DocumentCreation)
            scriptJsIpfs.setRunsOnSubFrames(True)
            self.webScripts.insert(scriptJsIpfs)

            # Install another script creating an IpfsApi instance
            # The API is available from Javascript as 'window.ipfs'

            script = QWebEngineScript()
            script.setSourceCode('\n'.join([
                "document.addEventListener('DOMContentLoaded', function () {",
                "window.ipfs = window.IpfsApi('{host}', '{port}');".format(
                    host=self.app.getIpfsConnectionParams().host,
                    port=self.app.getIpfsConnectionParams().apiPort),
                "})"]))
            script.setWorldId(QWebEngineScript.MainWorld)
            script.setInjectionPoint(QWebEngineScript.DocumentCreation)
            self.webScripts.insert(script)

    def installIpfsSchemeHandler(self):
        baFs   = QByteArray(b'fs')
        baIpfs = QByteArray(b'ipfs')
        baDweb = QByteArray(b'dweb')

        for scheme in [baFs, baIpfs, baDweb]:
            eHandler = self.webProfile.urlSchemeHandler(scheme)
            if not eHandler:
                self.webProfile.installUrlSchemeHandler(scheme,
                    self.app.ipfsSchemeHandler)

    def onPathVisited(self, path):
        # Called after a new IPFS object has been loaded in this tab
        self.app.task(self.tsVisitPath, path)

    @ipfsStatOp
    async def tsVisitPath(self, ipfsop, path, stat):
        # If automatic pinning is checked we pin the object
        if self.pinAll is True:
            self.pinPath(path, recursive=False, notify=False)

    def onClipboardIpfs(self, valid, cid, path):
        self.ui.loadFromClipboardButton.setEnabled(valid)

    def onToggledPinAll(self, checked):
        pass

    def onSavePage(self):
        page = self.webView.page()

        result = QFileDialog.getSaveFileName(None,
            'Select file',
            self.app.settingsMgr.getSetting(CFG_SECTION_BROWSER,
                CFG_KEY_DLPATH), '(*.*)')
        if not result:
            return

        page.save(result[0], QWebEngineDownloadItem.CompleteHtmlSaveFormat)

    def onHashmarkPage(self):
        if self.currentIpfsResource:
            addHashmark(self.app.marksLocal,
                    self.currentIpfsResource,
                    self.currentPageTitle,
                    stats=self.app.ipfsCtx.objectStats.get(
                        self.currentIpfsResource, {}))

    def onPinSuccess(self, f):
        self.app.systemTrayMessage('PIN', iPinSuccess(f.result()))

    def pinPath(self, path, recursive=True, notify=True):
        async def pinCoro(client, path):
            pinner = self.app.ipfsCtx.pinner
            onSuccess = None
            if notify is True:
                onSuccess = self.onPinSuccess
            await pinner.queue(path, recursive, onSuccess)

        self.app.ipfsTask(pinCoro, path)

    def printButtonClicked(self):
        # TODO: reinstate the printing button
        printer = QPrinter()
        dialog = QPrintDialog(printer, self)
        dialog.setModal(True)

        def success(ok):
            return ok

        if dialog.exec_() == QDialog.Accepted:
            currentPage = self.ui.webEngineView.page()
            currentPage.print(printer, success)

    def actionComboClicked(self, idx):
        if not self.currentIpfsResource:
            return
        if idx == 0:
            self.pinPath(self.currentIpfsResource, recursive=False)
        if idx == 1:
            self.pinPath(self.currentIpfsResource, recursive=True)

    def loadFromClipboardButtonClicked(self):
        current = self.app.clipTracker.getCurrent()
        if current:
            self.browseFsPath(current['path'])

    def onLoadIpfsCID(self):
        def onValidated(d):
            self.browseIpfsHash(d.getHash())

        runDialog(IPFSCIDInputDialog, title=iEnterIpfsCIDDialog(),
            accepted=onValidated)

    def onLoadIpfsMultipleCID(self):
        def onValidated(dlg):
            # Open a tab for every CID
            cids = dlg.getCIDs()
            for cid in cids:
                self.gWindow.addBrowserTab().browseIpfsHash(cid)

        runDialog(IPFSMultipleCIDInputDialog,
            title=iEnterIpfsCIDDialog(),
            accepted=onValidated)

    def onLoadIpns(self):
        text, ok = QInputDialog.getText(self,
                iEnterIpnsDialog(),
                iEnterIpns())
        if ok:
            self.browseIpnsHash(text)

    def onFollowIpns(self):
        runDialog(AddFeedDialog, self.app.marksLocal,
            self.currentIpfsResource,
            title=iFollowIpnsDialog())

    def onLoadHome(self):
        self.loadHomePage()

    def loadHomePage(self):
        homeUrl = self.app.settingsMgr.getSetting(CFG_SECTION_BROWSER,
            CFG_KEY_HOMEURL)
        self.enterUrl(QUrl(homeUrl))

    def refreshButtonClicked(self):
        self.ui.webEngineView.reload()

    def stopButtonClicked(self):
        self.ui.webEngineView.stop()
        self.ui.progressBar.setValue(0)

    def backButtonClicked(self):
        currentPage = self.ui.webEngineView.page()
        currentPage.history().back()

    def forwardButtonClicked(self):
        currentPage = self.ui.webEngineView.page()
        currentPage.history().forward()

    def onUrlChanged(self, url):
        if url.authority() == self.gatewayAuthority:
            self.currentIpfsResource = url.path()
            self.ui.urlZone.clear()
            # Content loaded from IPFS gateway, this is IPFS content
            self.ui.urlZone.insert(fsPath(url.path()))
            self.ipfsPathVisited.emit(self.currentIpfsResource)

            # Activate the follow action if this is IPNS
            # todo: better check on ipns path validity
            if self.currentIpfsResource.startswith('/ipns/'):
                self.followIpnsAction.setEnabled(True)
            else:
                self.followIpnsAction.setEnabled(False)
        else:
            self.currentIpfsResource = None
            self.ui.urlZone.clear()
            self.ui.urlZone.insert(url.toString())

    def onLoadFinished(self, ok):
        lenMax = 16
        pageTitle = self.ui.webEngineView.page().title()

        if pageTitle.startswith(self.gatewayAuthority):
            pageTitle = iNoTitle()

        self.currentPageTitle = pageTitle

        if len(pageTitle) > lenMax:
            pageTitle = '{0} ...'.format(pageTitle[0:lenMax])

        idx = self.gWindow.ui.tabWidget.indexOf(self)
        self.gWindow.ui.tabWidget.setTabText(idx, pageTitle)

        self.gWindow.ui.tabWidget.setTabToolTip(idx,
                self.currentPageTitle)

    def onIconChanged(self, icon):
        self.gWindow.ui.tabWidget.setTabIcon(self.tabPageIdx, icon)

    def onLoadProgress(self, progress):
        self.ui.progressBar.setValue(progress)

    def browseFsPath(self, path):
        self.enterUrl(QUrl('{0}:{1}'.format(SCHEME_IPFS, path)))

    def browseIpfsHash(self, ipfsHash):
        if not cidhelpers.cidValid(ipfsHash):
            return messageBox(iInvalidCID(ipfsHash))

        self.browseFsPath(joinIpfs(ipfsHash))

    def browseIpnsHash(self, ipnsHash):
        self.browseFsPath(joinIpns(ipnsHash))

    def enterUrl(self, url):
        self.ui.urlZone.clear()
        self.ui.urlZone.insert(url.toString())
        self.ui.webEngineView.load(url)

    def onUrlEdit(self):
        inputStr = self.ui.urlZone.text().strip()

        if cidhelpers.cidValid(inputStr):
            # Raw CID in the URL zone
            return self.browseIpfsHash(inputStr)

        url = QUrl(inputStr)
        scheme = url.scheme()

        if scheme in [SCHEME_FS, SCHEME_IPFS, SCHEME_DWEB]:
            self.enterUrl(url)
        elif scheme in ['http', 'https'] and \
                self.app.settingsMgr.allowHttpBrowsing is True:
            # Browse http urls if allowed
            self.enterUrl(url)
        else:
            messageBox(iInvalidUrl(inputStr))
