import functools
import os.path

from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QMenu
from PyQt5.QtWidgets import QInputDialog
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QToolButton
from PyQt5.QtWidgets import QTextBrowser
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QListView

from PyQt5.QtPrintSupport import *

from PyQt5.QtCore import QUrl
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QStandardItemModel
from PyQt5.QtGui import QStandardItem

from PyQt5 import QtWebEngineWidgets

from PyQt5.QtWebEngineWidgets import QWebEnginePage
from PyQt5.QtWebEngineWidgets import QWebEngineDownloadItem
from PyQt5.QtWebEngineWidgets import QWebEngineSettings
from PyQt5.QtWebEngineWidgets import QWebEngineContextMenuData

from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor

from PyQt5.QtGui import QKeySequence

from galacteek import log, ensure
from galacteek.ipfs.wrappers import *
from galacteek.ipfs import cidhelpers
from galacteek.ipfs import megabytes
from galacteek.ipfs.stat import StatInfo
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ipfs.cidhelpers import joinIpfs
from galacteek.ipfs.cidhelpers import joinIpns
from galacteek.ipfs.cidhelpers import cidValid
from galacteek.dweb.atom import DWEB_ATOM_FEEDFN
from galacteek.core.analyzer import ResourceAnalyzer

from galacteek.core.schemes import SCHEME_DWEB
from galacteek.core.schemes import SCHEME_ENS
from galacteek.core.schemes import SCHEME_FS
from galacteek.core.schemes import SCHEME_IPFS

from . import ui_browsertab
from .helpers import *
from .dialogs import *
from .hashmarks import *
from .i18n import *
from .clipboard import iCopyPathToClipboard
from .history import HistoryMatchesWidget
from .widgets import *
from ..appsettings import *

# i18n


def iOpenInTab():
    return QCoreApplication.translate('BrowserTabForm', 'Open link in new tab')


def iOpenHttpInTab():
    return QCoreApplication.translate('BrowserTabForm',
                                      'Open http/https link in new tab')


def iOpenWith():
    return QCoreApplication.translate('BrowserTabForm', 'Open with')


def iDownload():
    return QCoreApplication.translate('BrowserTabForm', 'Download')


def iSaveWebPage():
    return QCoreApplication.translate(
        'BrowserTabForm', 'Save page to the "Web Pages" folder')


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


class RequestInterceptor(QWebEngineUrlRequestInterceptor):
    def interceptRequest(self, info):
        pass


class CustomWebPage (QtWebEngineWidgets.QWebEnginePage):
    jsConsoleMessage = pyqtSignal(int, str, int, str)

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceId):
        self.jsConsoleMessage.emit(level, message, lineNumber, sourceId)

    def acceptNavigationRequest(self, url, nType, isMainFrame):
        return True


class JSConsoleWidget(QTextBrowser):
    def __init__(self, parent):
        super(JSConsoleWidget, self).__init__(parent)

        self.setReadOnly(True)
        self.setAcceptRichText(True)
        self.setObjectName('javascriptConsole')

    def showMessage(self, level, message, lineNumber, sourceId):
        sourcePath = IPFSPath(sourceId)

        if sourcePath.valid:
            source = str(sourcePath)
        else:
            source = sourceId

        if level == QWebEnginePage.InfoMessageLevel:
            levelH = 'INFO'
        elif level == QWebEnginePage.WarningMessageLevel:
            levelH = 'WARNING'
        elif level == QWebEnginePage.ErrorMessageLevel:
            levelH = 'ERROR'
        else:
            levelH = 'UNKNOWN'

        self.append('''
           <p>[{level}]
           <b>{source}</b> at line {line}: {message}
           </p>'''.format(
            source=source,
            level=levelH,
            line=lineNumber,
            message=message
        ))


class WebView(QtWebEngineWidgets.QWebEngineView):
    def __init__(self, browserTab, enablePlugins=False, parent=None):
        super().__init__(parent=parent)

        self.app = QCoreApplication.instance()
        self.linkInfoTimer = QTimer()
        self.linkInfoTimer.timeout.connect(self.onLinkInfoTimeout)

        self.webPage = CustomWebPage(self)
        self.webPage.jsConsoleMessage.connect(self.onJsMessage)
        self.webPage.linkHovered.connect(self.onLinkHovered)
        self.setPage(self.webPage)

        self.browserTab = browserTab

        self.webSettings = self.settings()
        self.webSettings.setAttribute(QWebEngineSettings.PluginsEnabled,
                                      enablePlugins)

    def onJsMessage(self, level, message, lineNo, sourceId):
        self.browserTab.jsConsole.showMessage(level, message, lineNo, sourceId)

    def onLinkInfoTimeout(self):
        self.browserTab.ui.linkInfosLabel.setText('')

    def onFollowTheAtom(self, ipfsPath):
        # TODO
        log.debug('Following atom feed: {}'.format(ipfsPath))

    def onLinkHovered(self, url):
        if not isinstance(url, str):
            return

        ipfsPath = IPFSPath(url)
        if ipfsPath.valid:
            self.browserTab.ui.linkInfosLabel.setText(ipfsPath.fullPath)
            if self.linkInfoTimer.isActive():
                self.linkInfoTimer.stop()

            self.linkInfoTimer.start(2200)

    def contextMenuEvent(self, event):
        analyzer = ResourceAnalyzer(parent=self)
        currentPage = self.page()
        contextMenuData = currentPage.contextMenuData()
        url = contextMenuData.linkUrl()
        mediaType = contextMenuData.mediaType()
        mediaUrl = contextMenuData.mediaUrl()

        ipfsPath = IPFSPath(url.toString())

        if mediaType != QWebEngineContextMenuData.MediaTypeNone and mediaUrl:
            mediaIpfsPath = IPFSPath(mediaUrl.toString())
        else:
            mediaIpfsPath = None

        if ipfsPath.valid:
            menu = QMenu()
            menu.addAction(getIcon('clipboard.png'),
                           iCopyPathToClipboard(),
                           functools.partial(self.app.setClipboardText,
                                             str(ipfsPath)
                                             ))
            menu.addSeparator()
            menu.addAction(getIcon('open.png'), iOpen(), functools.partial(
                ensure, self.app.resourceOpener.open(ipfsPath)))
            menu.addAction(getIcon('ipfs-logo-128-black.png'),
                           iOpenInTab(),
                           functools.partial(self.openInTab, ipfsPath))
            menu.addAction(getIcon('hashmarks.png'),
                           iHashmark(),
                           functools.partial(self.hashmarkPath, str(ipfsPath)))
            menu.addSeparator()
            menu.addAction(getIcon('pin.png'), iPin(),
                           functools.partial(self.browserTab.pinPath,
                                             ipfsPath.objPath))
            menu.addAction(
                getIcon('pin.png'),
                iPinRecursive(),
                functools.partial(
                    self.browserTab.pinPath,
                    ipfsPath.objPath,
                    True))

            def rscAnalyzed(fut, path, iMenu):
                try:
                    mimeType, stat = fut.result()
                except Exception:
                    pass
                else:
                    if mimeType and mimeType.isAtomFeed:
                        iMenu.addSeparator()
                        iMenu.addAction(
                            getIcon('atom-feed.png'),
                            'Follow Atom feed',
                            lambda: self.onFollowTheAtom(path)
                        )
            ensure(
                analyzer(ipfsPath),
                futcallback=lambda fut: rscAnalyzed(
                    fut,
                    ipfsPath,
                    menu
                )
            )

            menu.exec(event.globalPos())

        elif mediaIpfsPath and mediaIpfsPath.valid:
            # Needs refactor
            menu = QMenu()

            menu.addSeparator()
            menu.addAction(getIcon('clipboard.png'),
                           iCopyPathToClipboard(),
                           functools.partial(self.app.setClipboardText,
                                             str(mediaIpfsPath)
                                             ))
            menu.addSeparator()
            menu.addAction(getIcon('open.png'), iOpen(), functools.partial(
                ensure, self.app.resourceOpener.open(str(mediaIpfsPath))))
            menu.addAction(
                getIcon('ipfs-logo-128-black.png'),
                iOpenInTab(),
                functools.partial(
                    self.openInTab,
                    mediaIpfsPath))
            menu.addAction(getIcon('hashmarks.png'),
                           iHashmark(),
                           functools.partial(self.hashmarkPath,
                                             str(mediaIpfsPath)))
            menu.addSeparator()
            menu.addAction(getIcon('pin.png'), iPin(),
                           functools.partial(self.browserTab.pinPath,
                                             mediaIpfsPath.objPath))
            menu.addAction(getIcon('pin.png'), iPinRecursive(),
                           functools.partial(self.browserTab.pinPath,
                                             mediaIpfsPath.objPath, True))
            menu.addSeparator()

            async def rscMenuEnable(mainMenu, path, mimeType, stat, analyzer):
                if mimeType.isImage:
                    statInfo = StatInfo(stat)

                    if statInfo.valid and statInfo.dataLargerThan(
                            megabytes(4)):
                        return

                    codes = await analyzer.decodeQrCodes(str(path))
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
            menu = QMenu()
            scheme = url.scheme()

            if scheme in ['http', 'https']:
                menu.addAction(
                    iOpenHttpInTab(),
                    functools.partial(self.openHttpInTab, url)
                )

            menu.exec(event.globalPos())

    def hashmarkPath(self, path):
        ipfsPath = IPFSPath(path)
        if ipfsPath.valid:
            addHashmark(self.browserTab.app.marksLocal,
                        ipfsPath.fullPath,
                        ipfsPath.basename if ipfsPath.basename else iUnknown())

    def openInTab(self, path):
        tab = self.browserTab.gWindow.addBrowserTab()
        tab.browseFsPath(path)

    def openHttpInTab(self, url):
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
    reloadPressed = pyqtSignal()
    zoominPressed = pyqtSignal()
    zoomoutPressed = pyqtSignal()
    focusUrlPressed = pyqtSignal()

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
                if key == Qt.Key_L:
                    self.focusUrlPressed.emit()
                    return True
                if key == Qt.Key_Plus:
                    self.zoominPressed.emit()
                    return True
                if key == Qt.Key_Minus:
                    self.zoomoutPressed.emit()
                    return True
        return False


class URLInputWidget(QLineEdit):
    def __init__(self, history, historyView, parent):
        super(URLInputWidget, self).__init__(parent)

        self.app = QCoreApplication.instance()
        self.history = history
        self.historyMatches = historyView
        self.browser = parent

        self.setObjectName('urlZone')
        self.setMinimumWidth(400)
        self.setDragEnabled(True)

        self.urlEditing = False
        self.urlInput = None

        self.editTimer = QTimer(self)
        self.editTimer.timeout.connect(self.onTimeoutUrlEdit)
        self.editTimer.setSingleShot(True)

        self.returnPressed.connect(self.onReturnPressed)
        self.historyMatches.historyItemSelected.connect(
            self.onHistoryItemSelected)
        self.historyMatches.collapsed.connect(
            self.onHistoryCollapse)

    @property
    def editTimeoutMs(self):
        timeout = self.app.settingsMgr.urlHistoryEditTimeout
        return timeout if isinstance(timeout, int) else 1000

    def onReturnPressed(self):
        self.urlEditing = False
        self.browser.handleEditedUrl(self.text())

    def onHistoryCollapse(self):
        self.setFocus(Qt.PopupFocusReason)

    def focusInEvent(self, event):
        if event.reason() in [Qt.ShortcutFocusReason, Qt.MouseFocusReason,
                              Qt.PopupFocusReason, Qt.ActiveWindowFocusReason,
                              Qt.TabFocusReason]:
            self.urlEditing = True
            disconnectSig(self.textEdited, self.onUrlUserEdit)
            self.textEdited.connect(self.onUrlUserEdit)

        super(URLInputWidget, self).focusInEvent(event)

    def focusOutEvent(self, event):
        self.urlEditing = False
        disconnectSig(self.textEdited, self.onUrlUserEdit)
        self.editTimer.stop()
        super(URLInputWidget, self).focusOutEvent(event)

    def onUrlUserEdit(self, text):
        self.urlInput = text

        if not self.urlEditing or not self.history.enabled:
            return

        if not self.editTimer.isActive():
            self.editTimer.start(self.editTimeoutMs)
        else:
            self.editTimer.stop()
            self.editTimer.start(self.editTimeoutMs)

    def onTimeoutUrlEdit(self):
        ensure(self.historyLookup())

    async def historyLookup(self):
        if self.urlInput:
            matches = await self.history.match(self.urlInput)

            if len(matches) > 0:
                self.historyMatches.showMatches(matches)
                self.historyMatches.show()
                self.historyMatches.setFocus(Qt.OtherFocusReason)

            self.editTimer.stop()

    def onHistoryItemSelected(self, urlStr):
        self.historyMatches.hide()
        self.urlEditing = False

        url = QUrl(urlStr)

        if url.isValid():
            self.browser.enterUrl(url)


class HistoryMatchesWidgetOld(QListView):
    historyItemSelected = pyqtSignal(str)
    collapsed = pyqtSignal()

    def __init__(self, parent=None):
        super(HistoryMatchesWidget, self).__init__(parent)

        self.setObjectName('historySearchResults')
        self.activated.connect(self.onItemActivated)
        self.clicked.connect(self.onItemActivated)

        self.model = QStandardItemModel()
        self.setModel(self.model)

    def onItemActivated(self, idx):
        data = self.model.data(idx, Qt.EditRole)

        if isinstance(data, str):
            print('GOT', data)
            self.historyItemSelected.emit(data)

    def showMatches(self, matches):
        self.model.clear()
        for match in matches:
            if match['title']:
                text = '{title}: {url}'.format(
                    title=match['title'], url=match['url'])
            else:
                text = match['url']

            item = QStandardItem(text)
            item.setEditable(False)
            item.setData(match['url'], Qt.EditRole)
            self.model.invisibleRootItem().appendRow(item)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
            self.collapsed.emit()

        super(HistoryMatchesWidget, self).keyPressEvent(event)


class BrowserTab(GalacteekTab):
    # signals
    ipfsObjectVisited = pyqtSignal(IPFSPath)

    def __init__(self, gWindow, pinBrowsed=False):
        super(BrowserTab, self).__init__(gWindow)

        self.browserWidget = QWidget(self)
        self.browserWidget.setAttribute(Qt.WA_DeleteOnClose)

        self.jsConsoleWidget = JSConsoleWidget(self)
        self.jsConsoleWidget.setMaximumHeight(180)
        self.jsConsoleWidget.hide()

        self.ui = ui_browsertab.Ui_BrowserTabForm()
        self.ui.setupUi(self.browserWidget)

        self.vLayout.addWidget(self.browserWidget)
        self.ui.vLayoutConsole.addWidget(self.jsConsoleWidget)

        # URL zone
        self.historySearches = HistoryMatchesWidget(parent=self)
        self.historySearches.hide()
        self.urlZone = URLInputWidget(self.history, self.historySearches, self)
        self.ui.layoutHistory.addWidget(self.historySearches)
        self.ui.layoutUrl.addWidget(self.urlZone)

        # Install scheme handler early on
        self.webProfile = QtWebEngineWidgets.QWebEngineProfile.defaultProfile()
        self.installIpfsSchemeHandler()

        self.ui.webEngineView = WebView(
            self, enablePlugins=self.app.settingsMgr.ppApiPlugins,
            parent=self
        )
        self.ui.vLayoutBrowser.addWidget(self.ui.webEngineView)

        self.webScripts = self.webProfile.scripts()
        self.installScripts()

        self.ui.webEngineView.urlChanged.connect(self.onUrlChanged)
        self.ui.webEngineView.loadFinished.connect(self.onLoadFinished)
        self.ui.webEngineView.iconChanged.connect(self.onIconChanged)
        self.ui.webEngineView.loadProgress.connect(self.onLoadProgress)
        self.ui.webEngineView.titleChanged.connect(self.onTitleChanged)

        self.ui.backButton.clicked.connect(self.backButtonClicked)
        self.ui.forwardButton.clicked.connect(self.forwardButtonClicked)

        self.ui.reloadPageButton.clicked.connect(self.refreshButtonClicked)
        self.ui.stopButton.clicked.connect(self.stopButtonClicked)

        self.ui.backButton.setEnabled(False)
        self.ui.forwardButton.setEnabled(False)
        self.ui.stopButton.setEnabled(False)

        self.ui.linkInfosLabel.setObjectName('linkInfos')
        self.ui.jsConsoleButton.setCheckable(True)
        self.ui.jsConsoleButton.toggled.connect(self.onJsConsoleToggle)

        self.ui.loadFromClipboardButton.clicked.connect(
            self.loadFromClipboardButtonClicked)

        # Save page button, visible when non-IPFS content is displayed
        saveIcon = getMimeIcon('text/html')
        self.savePageButton = PopupToolButton(
            saveIcon, mode=QToolButton.InstantPopup, parent=self
        )
        self.savePageButton.setToolTip(iSaveWebPage())
        self.savePageButton.menu.addAction(saveIcon,
                                           iSaveWebPage(),
                                           self.onSavePage)
        self.savePageButton.setEnabled(False)

        self.hashmarkPageAction = QAction(getIcon('hashmark-black.png'),
                                          iHashmarkThisPage(), self,
                                          shortcut=QKeySequence('Ctrl+b'),
                                          triggered=self.onHashmarkPage)
        self.ui.hashmarkThisPage.setDefaultAction(self.hashmarkPageAction)
        self.ui.hashmarkThisPage.setEnabled(False)

        self.ui.hLayoutCtrl.addWidget(self.savePageButton)

        # Setup the tool button for browsing IPFS content
        self.loadIpfsMenu = QMenu()
        self.loadIpfsCIDAction = QAction(getIconIpfsIce(),
                                         iBrowseIpfsCID(), self,
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
        evfilter.focusUrlPressed.connect(self.onFocusUrl)
        self.installEventFilter(evfilter)

        self.resolveTimer = QTimer(self)
        self.resolveTimerEnsMs = 7000
        self.urlInput = None

        self.app.clipTracker.clipboardPathProcessed.connect(
            self.onClipboardIpfs)
        self.ipfsObjectVisited.connect(self.onPathVisited)

        self._currentIpfsResource = None
        self._currentUrl = None
        self.currentPageTitle = None

    @property
    def history(self):
        return self.gWindow.app.urlHistory

    @property
    def webView(self):
        return self.ui.webEngineView

    @property
    def currentUrl(self):
        return self._currentUrl

    @property
    def jsConsole(self):
        return self.jsConsoleWidget

    @property
    def tabPage(self):
        return self.gWindow.tabWidget.widget(self.tabPageIdx)

    @property
    def tabPageIdx(self):
        return self.gWindow.tabWidget.indexOf(self)

    @property
    def gatewayAuthority(self):
        return self.app.gatewayAuthority

    @property
    def gatewayUrl(self):
        return self.app.gatewayUrl

    @property
    def pinAll(self):
        return self.ui.pinAllButton.isChecked()

    @property
    def currentIpfsResource(self):
        return self._currentIpfsResource

    def installScripts(self):
        self.webScripts = self.webProfile.scripts()

        exSc = self.webScripts.findScript('ipfs-http-client')
        if self.app.settingsMgr.jsIpfsApi is True and exSc.isNull():
            log.debug('Adding ipfs-http-client scripts')
            for script in self.app.scriptsIpfs:
                self.webScripts.insert(script)

    def installIpfsSchemeHandler(self):
        for scheme in [SCHEME_DWEB, SCHEME_FS]:
            eHandler = self.webProfile.urlSchemeHandler(scheme.encode())
            if not eHandler:
                self.webProfile.installUrlSchemeHandler(
                    scheme.encode(), self.app.ipfsSchemeHandler)

        eHandler = self.webProfile.urlSchemeHandler(SCHEME_ENS.encode())
        if not eHandler:
            self.webProfile.installUrlSchemeHandler(
                SCHEME_ENS.encode(), self.app.ensSchemeHandler)

        self.app.ensSchemeHandler.domainResolved.connect(self.onEnsResolved)

    def onPathVisited(self, ipfsPath):
        # Called after a new IPFS object has been loaded in this tab

        if ipfsPath.valid:
            ensure(self.tsVisitPath(ipfsPath.objPath))

            if ipfsPath.basename and ipfsPath.basename == DWEB_ATOM_FEEDFN:
                reply = questionBox(
                    'Atom feed',
                    'This looks like an Atom feed. Try and follow the atom ?'
                )
                if reply is True:
                    # TODO
                    return

    @ipfsStatOp
    async def tsVisitPath(self, ipfsop, path, stat):
        # If automatic pinning is checked we pin the object
        if self.pinAll is True:
            self.pinPath(path, recursive=False, notify=False)

    def onJsConsoleToggle(self, checked):
        self.jsConsoleWidget.setVisible(checked)

    def onClipboardIpfs(self, pathObj):
        self.ui.loadFromClipboardButton.setEnabled(True)

    def onToggledPinAll(self, checked):
        pass

    def onFocusUrl(self):
        self.focusUrlZone(True, reason=Qt.ShortcutFocusReason)

    def focusUrlZone(self, select=False, reason=Qt.OtherFocusReason):
        self.urlZone.setFocus(reason)

        if select:
            self.urlZone.setSelection(0, len(self.urlZone.text()))

    def onReloadPage(self):
        self.ui.webEngineView.reload()

    def onSavePage(self):
        tmpd = self.app.tempDirCreate(self.app.tempDirWeb)
        if tmpd is None:
            return messageBox('Cannot create temporary directory')

        page = self.webView.page()

        url = page.url()
        filename = url.fileName()

        if filename == '' or cidValid(filename):
            filename = 'index.html'

        path = os.path.join(tmpd, filename)
        page.save(path, QWebEngineDownloadItem.CompleteHtmlSaveFormat)

    def onHashmarkClicked(self, path, title):
        ipfsPath = IPFSPath(path)

        if ipfsPath.valid:
            self.browseFsPath(ipfsPath)

    def onHashmarkPage(self):
        if self.currentIpfsResource and self.currentIpfsResource.valid:
            addHashmark(self.app.marksLocal,
                        self.currentIpfsResource.fullPath,
                        self.currentPageTitle,
                        stats=self.app.ipfsCtx.objectStats.get(
                            self.currentIpfsResource.path, {}))
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
        if isinstance(path, str):
            ensure(self.pinQueuePath(path, recursive, notify))
        elif isinstance(path, IPFSPath):
            ensure(self.pinQueuePath(path.objPath, recursive, notify))

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

        self.pinPath(self.currentIpfsResource.objPath, recursive=False)

    def onPinRecursive(self):
        if not self.currentIpfsResource:
            return messageBox(iNotAnIpfsResource())

        self.pinPath(self.currentIpfsResource.objPath, recursive=True)

    def loadFromClipboardButtonClicked(self):
        current = self.app.clipTracker.getCurrent()
        if current:
            self.browseFsPath(IPFSPath(current.fullPath))

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
                  self.currentIpfsResource.objPath,
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
            urlString = url.toDisplayString(
                QUrl.RemoveAuthority | QUrl.RemoveScheme)

            self._currentIpfsResource = IPFSPath(urlString)

            if self.currentIpfsResource.valid:
                log.debug('Current IPFS object: {0}'.format(
                    repr(self.currentIpfsResource)))

                url = QUrl(self.currentIpfsResource.dwebUrl)
                self.urlZone.clear()
                self.urlZone.insert(url.toString())

                self.ui.hashmarkThisPage.setEnabled(True)
                self.ui.pinToolButton.setEnabled(True)

                self.ipfsObjectVisited.emit(self.currentIpfsResource)

                self._currentUrl = url
            else:
                log.debug('Invalid IPFS path: {0}'.format(urlString))

            # Activate the follow action if this is a root IPNS address
            self.followIpnsAction.setEnabled(
                self.currentIpfsResource.isIpnsRoot)
        else:
            self._currentIpfsResource = None
            self.urlZone.clear()
            self.urlZone.insert(url.toString())
            self._currentUrl = url

        if url.scheme() in [SCHEME_ENS]:
            self.history.record(url.toString(), None)

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

        idx = self.gWindow.tabWidget.indexOf(self)
        self.gWindow.tabWidget.setTabText(idx, pageTitle)
        self.gWindow.tabWidget.setTabToolTip(idx, self.currentPageTitle)

        if self.currentPageTitle != iNoTitle() and self.currentUrl and \
                self.currentUrl.isValid():
            # Only record those schemes in the history
            if self.currentUrl.scheme() in [SCHEME_DWEB, SCHEME_IPFS]:
                self.history.record(self.currentUrl.toString(),
                                    self.currentPageTitle)

    def onLoadFinished(self, ok):
        self.ui.stopButton.setEnabled(False)
        self.savePageButton.setEnabled(True)

    def onIconChanged(self, icon):
        self.gWindow.tabWidget.setTabIcon(self.tabPageIdx, icon)

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
        if isinstance(path, str):
            self.enterUrl(QUrl('{0}:{1}'.format(SCHEME_DWEB, path)))
        elif isinstance(path, IPFSPath):
            if path.valid:
                self.enterUrl(QUrl('{0}:{1}'.format(SCHEME_DWEB,
                                                    path.fullPath)))
            else:
                messageBox(iInvalidUrl(path.fullPath))

    def browseIpfsHash(self, ipfsHash):
        if not cidhelpers.cidValid(ipfsHash):
            return messageBox(iInvalidCID(ipfsHash))

        self.browseFsPath(IPFSPath(joinIpfs(ipfsHash)))

    def browseIpnsHash(self, ipnsHash):
        self.browseFsPath(IPFSPath(joinIpns(ipnsHash)))

    def enterUrl(self, url):
        self.urlZone.urlEditing = False
        self.urlZone.clearFocus()

        self.savePageButton.setEnabled(False)
        log.debug('Entering URL {}'.format(url.toString()))

        def onEnsTimeout():
            if not self.urlZone.isEnabled():
                self.urlZone.setEnabled(True)

        if url.scheme() == SCHEME_ENS:
            self.urlZone.setEnabled(False)
            self.resolveTimer.timeout.connect(onEnsTimeout)
            self.resolveTimer.start(self.resolveTimerEnsMs)
        else:
            self.urlZone.setEnabled(True)

        self.urlZone.clear()
        self.urlZone.insert(url.toString())
        self.ui.webEngineView.load(url)

    def handleEditedUrl(self, inputStr):
        if cidhelpers.cidValid(inputStr):
            # Raw CID in the URL zone
            return self.browseIpfsHash(inputStr)

        url = QUrl(inputStr)
        scheme = url.scheme()

        if scheme in [SCHEME_FS, SCHEME_ENS, SCHEME_IPFS, SCHEME_DWEB]:
            self.enterUrl(url)
        elif scheme in ['http', 'https'] and \
                self.app.settingsMgr.allowHttpBrowsing is True:
            # Browse http urls if allowed
            self.enterUrl(url)
        else:
            self.enterUrl(QUrl('dweb:/ipns/{input}'.format(input=inputStr)))

    def onEnsResolved(self, domain, path):
        self.urlZone.setEnabled(True)

    def onZoomIn(self):
        cFactor = self.webView.zoomFactor()
        self.webView.setZoomFactor(cFactor + 0.25)

    def onZoomOut(self):
        cFactor = self.webView.zoomFactor()
        self.webView.setZoomFactor(cFactor - 0.25)
