import functools

from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QMenu
from PyQt5.QtWidgets import QInputDialog
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QToolButton
from PyQt5.QtWidgets import QFileDialog

from PyQt5.QtPrintSupport import *

from PyQt5.QtCore import QUrl
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtCore import QTimer

from PyQt5 import QtWebEngineWidgets
from PyQt5 import QtWebEngineCore
from PyQt5.QtWebEngineWidgets import QWebEngineDownloadItem
from PyQt5.QtWebEngineWidgets import QWebEngineSettings
from PyQt5.QtWebEngineWidgets import QWebEngineContextMenuData
from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor

from PyQt5.Qt import QByteArray
from PyQt5.QtGui import QKeySequence

from yarl import URL
import os.path

from galacteek import log, ensure
from galacteek.ipfs.wrappers import *
from galacteek.ipfs import cidhelpers
from galacteek.ipfs.cidhelpers import joinIpfs
from galacteek.ipfs.cidhelpers import joinIpns

from . import ui_browsertab
from .resource import ResourceAnalyzer
from .helpers import *
from .dialogs import *
from .hashmarks import *
from .i18n import *
from .clipboard import iCopyPathToClipboard
from .widgets import *
from ..appsettings import *

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
    return QCoreApplication.translate(
        'BrowserTabForm',
        '{0} is an invalid IPFS CID (Content IDentifier)').format(text)


def iNotAnIpfsResource():
    return QCoreApplication.translate(
        'BrowserTabForm',
        'Not an IPFS resource')


def makeDwebPath(path):
    return '{0}:{1}'.format(SCHEME_DWEB, path)


def usesIpfsNs(url):
    return url.startswith('{0}:/'.format(SCHEME_DWEB))


class IPFSSchemeHandler(QtWebEngineCore.QWebEngineUrlSchemeHandler):
    def __init__(self, app, parent=None):
        QtWebEngineCore.QWebEngineUrlSchemeHandler.__init__(self, parent)
        self.app = app

    def requestStarted(self, request):
        url = request.requestUrl()

        if url is None:
            return

        scheme = url.scheme()
        path = url.path()

        log.debug(
            'IPFS scheme handler req: {url} {scheme} {path} {method}'.format(
                url=url.toString(), scheme=scheme, path=path,
                method=request.requestMethod()))

        def redirectIpfs(path):
            yUrl = URL(url.toString())

            if len(yUrl.parts) < 3:
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

            if not isinstance(path, str):
                return

            if path.startswith('/ipfs/') or path.startswith('/ipns/'):
                try:
                    return redirectIpfs(path)
                except Exception as err:
                    log.debug('Exception in request'.format(exc_info=err))


class RequestInterceptor(QWebEngineUrlRequestInterceptor):
    def interceptRequest(self, info):
        pass


class CustomWebPage (QtWebEngineWidgets.QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceId):
        log.debug(
            'JS: level: {0}, source: {1}, line: {2}, message: {3}'.format(
                level, sourceId, lineNumber, message))


class WebView(QtWebEngineWidgets.QWebEngineView):
    def __init__(self, browserTab, enablePlugins=False, parent=None):
        super().__init__(parent=parent)

        self.app = QCoreApplication.instance()
        self.linkInfoTimer = QTimer()
        self.linkInfoTimer.timeout.connect(self.onLinkInfoTimeout)

        self.webPage = CustomWebPage(self)
        self.webPage.linkHovered.connect(self.onLinkHovered)
        self.setPage(self.webPage)

        self.browserTab = browserTab

        self.webSettings = self.settings()
        self.webSettings.setAttribute(QWebEngineSettings.PluginsEnabled,
                                      enablePlugins)

    def onLinkInfoTimeout(self):
        self.browserTab.ui.linkInfosLabel.setText('')

    def onLinkHovered(self, url):
        if not isinstance(url, str):
            return

        ipfsPath = cidhelpers.ipfsPathExtract(url)
        if ipfsPath:
            self.browserTab.ui.linkInfosLabel.setText(ipfsPath)
            if self.linkInfoTimer.isActive():
                self.linkInfoTimer.stop()
            self.linkInfoTimer.start(2200)

    def contextMenuEvent(self, event):
        currentPage = self.page()
        contextMenuData = currentPage.contextMenuData()
        url = contextMenuData.linkUrl()
        mediaType = contextMenuData.mediaType()
        mediaUrl = contextMenuData.mediaUrl()

        ipfsPath = cidhelpers.ipfsPathExtract(url.toString())

        if mediaType != QWebEngineContextMenuData.MediaTypeNone and mediaUrl:
            mediaIpfsPath = cidhelpers.ipfsPathExtract(mediaUrl.toString())
        else:
            mediaIpfsPath = None

        if ipfsPath:
            menu = QMenu()
            menu.addAction(getIcon('clipboard.png'),
                           iCopyPathToClipboard(),
                           functools.partial(self.app.setClipboardText,
                                             ipfsPath
                                             ))
            menu.addSeparator()
            menu.addAction(getIcon('open'), iOpen(), functools.partial(
                ensure, self.app.resourceOpener.open(ipfsPath)))
            menu.addAction(getIcon('ipfs-logo-128-black.png'),
                           iOpenInTab(),
                           functools.partial(self.openInTab, ipfsPath))
            menu.addAction(getIcon('hashmarks.png'),
                           iHashmark(),
                           functools.partial(self.hashmarkPath, ipfsPath))
            menu.addSeparator()
            menu.addAction(getIcon('pin.png'), iPin(), lambda:
                           self.pinPath(ipfsPath))
            menu.addAction(getIcon('pin.png'), iPinRecursive(), lambda:
                           self.pinPath(ipfsPath, True))
            menu.exec(event.globalPos())
        elif mediaIpfsPath:
            # Needs refactor
            analyzer = ResourceAnalyzer()

            menu = QMenu()

            menu.addSeparator()
            menu.addAction(getIcon('clipboard.png'),
                           iCopyPathToClipboard(),
                           functools.partial(self.app.setClipboardText,
                                             mediaIpfsPath
                                             ))
            menu.addSeparator()
            menu.addAction(getIcon('open'), iOpen(), functools.partial(
                ensure, self.app.resourceOpener.open(mediaIpfsPath)))
            menu.addAction(getIcon('ipfs-logo-128-black.png'),
                           iOpenInTab(),
                           functools.partial(self.openInTab, mediaIpfsPath))
            menu.addAction(getIcon('hashmarks.png'),
                           iHashmark(),
                           functools.partial(self.hashmarkPath, mediaIpfsPath))
            menu.addSeparator()
            menu.addAction(getIcon('pin.png'), iPin(), lambda:
                           self.pinPath(mediaIpfsPath))
            menu.addAction(getIcon('pin.png'), iPinRecursive(), lambda:
                           self.pinPath(mediaIpfsPath, True))
            menu.addSeparator()

            async def rscMenuEnable(mainMenu, path, mimeType, stat, analyzer):
                if mimeType.isImage:
                    if stat:
                        size = stat.get('DataSize')

                        if isinstance(size, int) and size > (1024 * 1024 * 4):
                            return

                    codes = await analyzer.decodeQrCodes(path)
                    if codes:
                        codesMenu = qrCodesMenuBuilder(
                            codes, self.app.resourceOpener, parent=mainMenu)
                        mainMenu.addMenu(codesMenu)

            def rscAnalyzed(fut, path, mediaType, analyzer):
                try:
                    mimeType, stat = fut.result()
                except Exception:
                    pass
                else:
                    ensure(rscMenuEnable(menu, path, mimeType, stat,
                                         analyzer))

            ensure(
                analyzer(mediaIpfsPath),
                futcallback=lambda fut: rscAnalyzed(
                    fut,
                    mediaIpfsPath,
                    mediaType,
                    analyzer
                )
            )

            menu.exec(event.globalPos())
        else:
            # Non-IPFS URL
            menu = currentPage.createStandardContextMenu()
            if menu:
                menu.exec(event.globalPos())

    def hashmarkPath(self, path):
        basename = os.path.basename(path)
        addHashmark(self.browserTab.app.marksLocal,
                    path, basename if basename else '')

    def openWithMediaPlayer(self, menudata):
        url = menudata.linkUrl()
        self.browserTab.gWindow.mediaPlayerQueue(url.path())

    def pinPath(self, path, recursive=False):
        self.browserTab.pinPath(path, recursive=recursive)

    def openInTab(self, path):
        tab = self.browserTab.gWindow.addBrowserTab()
        tab.browseFsPath(path)

    def downloadLink(self, menudata):
        url = menudata.linkUrl()
        self.page().download(url, None)

    def createWindow(self, wtype):
        pass


class BrowserKeyFilter(QObject):
    hashmarkPressed = pyqtSignal()
    savePagePressed = pyqtSignal()
    reloadPressed = pyqtSignal()
    zoominPressed = pyqtSignal()
    zoomoutPressed = pyqtSignal()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            modifiers = event.modifiers()

            key = event.key()
            if key == Qt.Key_F5:
                self.reloadPressed.emit()
                return True

            if modifiers & Qt.ControlModifier:
                if key == Qt.Key_B:
                    self.hashmarkPressed.emit()
                    return True
                if key == Qt.Key_S:
                    self.savePagePressed.emit()
                    return True
                if key == Qt.Key_R:
                    self.reloadPressed.emit()
                    return True
                if key == Qt.Key_Plus:
                    self.zoominPressed.emit()
                    return True
                if key == Qt.Key_Minus:
                    self.zoomoutPressed.emit()
                    return True
        return False


class BrowserTab(GalacteekTab):
    # signals
    ipfsPathVisited = pyqtSignal(str)

    def __init__(self, gWindow, pinBrowsed=False):
        super(BrowserTab, self).__init__(gWindow)

        self.browserWidget = QWidget()
        self.vLayout.addWidget(self.browserWidget)

        self.ui = ui_browsertab.Ui_BrowserTabForm()
        self.ui.setupUi(self.browserWidget)

        # Install scheme handler early on
        self.webProfile = QtWebEngineWidgets.QWebEngineProfile.defaultProfile()
        self.installIpfsSchemeHandler()

        self.ui.webEngineView = WebView(
            self, enablePlugins=self.app.settingsMgr.ppApiPlugins)
        self.ui.vLayoutBrowser.addWidget(self.ui.webEngineView)

        self.webScripts = self.webProfile.scripts()
        self.installScripts()

        self.ui.webEngineView.urlChanged.connect(self.onUrlChanged)
        self.ui.webEngineView.loadFinished.connect(self.onLoadFinished)
        self.ui.webEngineView.iconChanged.connect(self.onIconChanged)
        self.ui.webEngineView.loadProgress.connect(self.onLoadProgress)
        self.ui.webEngineView.titleChanged.connect(self.onTitleChanged)

        self.ui.urlZone.returnPressed.connect(self.onUrlEdit)
        self.ui.backButton.clicked.connect(self.backButtonClicked)
        self.ui.forwardButton.clicked.connect(self.forwardButtonClicked)

        self.ui.reloadPageButton.clicked.connect(self.refreshButtonClicked)
        self.ui.stopButton.clicked.connect(self.stopButtonClicked)

        self.ui.backButton.setEnabled(False)
        self.ui.forwardButton.setEnabled(False)
        self.ui.stopButton.setEnabled(False)

        self.ui.linkInfosLabel.setObjectName('linkInfos')

        self.ui.loadFromClipboardButton.clicked.connect(
            self.loadFromClipboardButtonClicked)
        self.ui.loadFromClipboardButton.setEnabled(
            self.app.clipTracker.hasIpfs)

        self.hashmarkMgrButton = HashmarkMgrButton(
            marks=self.app.marksLocal)
        self.hashmarkPageAction = QAction(getIcon('hashmarks.png'),
                                          iHashmark(), self,
                                          shortcut=QKeySequence('Ctrl+b'),
                                          triggered=self.onHashmarkPage)
        self.hashmarkMgrButton.setDefaultAction(self.hashmarkPageAction)

        self.hashmarkMgrButton.hashmarkClicked.connect(self.onHashmarkClicked)

        self.hashmarkMgrButton.updateMenu()
        self.ui.hLayoutCtrl.addWidget(self.hashmarkMgrButton)

        # Setup the tool button for browsing IPFS content
        self.loadIpfsMenu = QMenu()
        self.loadIpfsCIDAction = QAction(getIconIpfsIce(),
                                         iBrowseIpfsCID(), self,
                                         shortcut=QKeySequence('Ctrl+l'),
                                         triggered=self.onLoadIpfsCID)
        self.loadIpfsMultipleCIDAction = QAction(
            getIconIpfsIce(),
            iBrowseIpfsMultipleCID(),
            self,
            triggered=self.onLoadIpfsMultipleCID)
        self.loadIpnsAction = QAction(getIconIpfsWhite(),
                                      iBrowseIpnsHash(), self,
                                      triggered=self.onLoadIpns)
        self.followIpnsAction = QAction(getIconIpfsWhite(),
                                        iFollow(), self,
                                        triggered=self.onFollowIpns)
        self.loadHomeAction = QAction(getIcon('go-home.png'),
                                      iBrowseHomePage(), self,
                                      triggered=self.onLoadHome)

        self.loadIpfsMenu.addAction(self.loadIpfsCIDAction)
        self.loadIpfsMenu.addAction(self.loadIpfsMultipleCIDAction)
        self.loadIpfsMenu.addAction(self.loadIpnsAction)
        self.loadIpfsMenu.addAction(self.followIpnsAction)
        self.loadIpfsMenu.addAction(self.loadHomeAction)

        self.ui.loadIpfsButton.setMenu(self.loadIpfsMenu)
        self.ui.loadIpfsButton.setPopupMode(QToolButton.InstantPopup)
        self.ui.loadIpfsButton.clicked.connect(self.onLoadIpfsCID)

        self.ui.pBarBrowser.setTextVisible(False)
        self.ui.pinAllButton.setCheckable(True)
        self.ui.pinAllButton.setAutoRaise(True)

        if pinBrowsed:
            self.ui.pinAllButton.setChecked(True)
        else:
            self.ui.pinAllButton.setChecked(self.gWindow.pinAllGlobalChecked)

        self.ui.pinAllButton.toggled.connect(self.onToggledPinAll)

        # PIN tool button
        iconPin = getIcon('pin.png')

        pinMenu = QMenu()
        pinMenu.addAction(iconPin, iPinThisPage(), self.onPinSingle)
        pinMenu.addAction(iconPin, iPinRecursive(), self.onPinRecursive)

        self.ui.pinToolButton.setMenu(pinMenu)
        self.ui.pinToolButton.setIcon(iconPin)
        self.ui.pinToolButton.setText(iPin())

        self.ui.zoomInButton.clicked.connect(self.onZoomIn)
        self.ui.zoomOutButton.clicked.connect(self.onZoomOut)

        # Event filter
        evfilter = BrowserKeyFilter(self)
        evfilter.hashmarkPressed.connect(self.onHashmarkPage)
        evfilter.reloadPressed.connect(self.onReloadPage)
        evfilter.zoominPressed.connect(self.onZoomIn)
        evfilter.zoomoutPressed.connect(self.onZoomOut)
        self.installEventFilter(evfilter)

        self.app.clipTracker.clipboardHasIpfs.connect(self.onClipboardIpfs)
        self.ipfsPathVisited.connect(self.onPathVisited)

        self.currentUrl = None
        self.currentIpfsResource = None
        self.currentIpfsUrl = None
        self.currentPageTitle = None
        self.setAttribute(Qt.WA_DeleteOnClose)

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
        self.webScripts = self.webProfile.scripts()

        exSc = self.webScripts.findScript('ipfs-http-client')
        if self.app.settingsMgr.jsIpfsApi is True and exSc.isNull():
            log.debug('Adding ipfs-http-client scripts')
            for script in self.app.scriptsIpfs:
                self.webScripts.insert(script)

    def installIpfsSchemeHandler(self):
        baFs = QByteArray(b'fs')
        baIpfs = QByteArray(b'ipfs')
        baDweb = QByteArray(b'dweb')

        for scheme in [baFs, baIpfs, baDweb]:
            eHandler = self.webProfile.urlSchemeHandler(scheme)
            if not eHandler:
                self.webProfile.installUrlSchemeHandler(
                    scheme, self.app.ipfsSchemeHandler)

    def onPathVisited(self, path):
        # Called after a new IPFS object has been loaded in this tab
        self.app.task(self.tsVisitPath, path)

    @ipfsStatOp
    async def tsVisitPath(self, ipfsop, path, stat):
        # If automatic pinning is checked we pin the object
        if self.pinAll is True:
            self.pinPath(path, recursive=False, notify=False)

    def onClipboardIpfs(self, valid, path):
        self.ui.loadFromClipboardButton.setEnabled(valid)

    def onToggledPinAll(self, checked):
        pass

    def onReloadPage(self):
        self.ui.webEngineView.reload()

    def onSavePage(self):
        page = self.webView.page()

        result = QFileDialog.getSaveFileName(
            None, 'Select file', self.app.settingsMgr.getSetting(
                CFG_SECTION_BROWSER, CFG_KEY_DLPATH), '(*.*)')
        if not result:
            return

        page.save(result[0], QWebEngineDownloadItem.CompleteHtmlSaveFormat)

    def onHashmarkClicked(self, path, title):
        self.browseFsPath(path)

    def onHashmarkPage(self):
        if self.currentIpfsResource:
            addHashmark(self.app.marksLocal,
                        self.currentIpfsUrl,
                        self.currentPageTitle,
                        stats=self.app.ipfsCtx.objectStats.get(
                            self.currentIpfsResource, {}))
        else:
            messageBox(iNotAnIpfsResource())

    def onPinSuccess(self, f):
        self.app.systemTrayMessage('PIN', iPinSuccess(f.result()))

    @ipfsOp
    async def pinQueuePath(self, ipfsop, path, recursive, notify):
        log.debug('Pinning object {0} (recursive: {1})'.format(path,
                                                               recursive))
        onSuccess = None
        if notify is True:
            onSuccess = self.onPinSuccess
        await ipfsop.ctx.pinner.queue(path, recursive, onSuccess,
                                      qname='browser')

    def pinPath(self, path, recursive=True, notify=True):
        ensure(self.pinQueuePath(path, recursive, notify))

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

    def onPinSingle(self):
        if not self.currentIpfsResource:
            return messageBox(iNotAnIpfsResource())

        self.pinPath(self.currentIpfsResource, recursive=False)

    def onPinRecursive(self):
        if not self.currentIpfsResource:
            return messageBox(iNotAnIpfsResource())

        self.pinPath(self.currentIpfsResource, recursive=True)

    def loadFromClipboardButtonClicked(self):
        current = self.app.clipTracker.getCurrent()
        if current:
            self.browseFsPath(current.path)

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
        self.ui.pBarBrowser.setValue(0)
        self.ui.stopButton.setEnabled(False)

    def backButtonClicked(self):
        currentPage = self.ui.webEngineView.page()
        currentPage.history().back()

    def forwardButtonClicked(self):
        currentPage = self.ui.webEngineView.page()
        currentPage.history().forward()

    def onUrlChanged(self, url):
        if url.authority() == self.gatewayAuthority:
            # Content loaded from IPFS gateway, this is IPFS content
            self.currentIpfsResource = url.path()
            self.ui.urlZone.clear()

            stripped = url.toDisplayString(
                QUrl.RemoveAuthority | QUrl.RemoveScheme)
            self.currentIpfsUrl = stripped

            self.ui.urlZone.insert(makeDwebPath(stripped))
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

        currentPage = self.webView.page()

        if currentPage:
            history = currentPage.history()
            self.ui.backButton.setEnabled(history.canGoBack())
            self.ui.forwardButton.setEnabled(history.canGoForward())

    def onTitleChanged(self, pageTitle):
        if pageTitle.startswith(self.gatewayAuthority):
            pageTitle = iNoTitle()

        self.currentPageTitle = pageTitle

        lenMax = 16
        if len(pageTitle) > lenMax:
            pageTitle = '{0} ...'.format(pageTitle[0:lenMax])

        idx = self.gWindow.ui.tabWidget.indexOf(self)
        self.gWindow.ui.tabWidget.setTabText(idx, pageTitle)
        self.gWindow.ui.tabWidget.setTabToolTip(idx,
                                                self.currentPageTitle)

    def onLoadFinished(self, ok):
        self.ui.stopButton.setEnabled(False)

    def onIconChanged(self, icon):
        self.gWindow.ui.tabWidget.setTabIcon(self.tabPageIdx, icon)

    def onLoadProgress(self, progress):
        self.ui.pBarBrowser.setValue(progress)
        self.ui.stopButton.setEnabled(progress >= 0 and progress < 100)

        if progress == 100:
            self.ui.pBarBrowser.setStyleSheet(
                '''QProgressBar::chunk#pBarBrowser {
                    background-color: #244e66;
                }''')
            self.loop.call_later(
                1,
                self.ui.pBarBrowser.setStyleSheet,
                '''QProgressBar::chunk#pBarBrowser {
                    background-color: transparent;
                }''')
        else:
            self.ui.pBarBrowser.setStyleSheet(
                '''QProgressBar::chunk#pBarBrowser {
                    background-color: #7f8491;
                }''')

    def browseFsPath(self, path):
        self.enterUrl(QUrl('{0}:{1}'.format(SCHEME_DWEB, path)))

    def browseIpfsHash(self, ipfsHash):
        if not cidhelpers.cidValid(ipfsHash):
            return messageBox(iInvalidCID(ipfsHash))

        self.browseFsPath(joinIpfs(ipfsHash))

    def browseIpnsHash(self, ipnsHash):
        self.browseFsPath(joinIpns(ipnsHash))

    def enterUrl(self, url):
        log.debug('Entering URL {}'.format(url.toString()))
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

    def onZoomIn(self):
        cFactor = self.webView.zoomFactor()
        self.webView.setZoomFactor(cFactor + 0.25)

    def onZoomOut(self):
        cFactor = self.webView.zoomFactor()
        self.webView.setZoomFactor(cFactor - 0.25)
