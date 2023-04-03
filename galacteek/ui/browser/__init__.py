import asyncio
import functools
import os.path
import re
import aioipfs
import validators
from yarl import URL
from urllib.parse import quote

from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QActionGroup
from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QInputDialog
from PyQt5.QtWidgets import QMenu
from PyQt5.QtWidgets import QToolButton
from PyQt5.QtWidgets import QTextBrowser
from PyQt5.QtWidgets import QTextEdit
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QWidgetAction
from PyQt5.QtWidgets import QGraphicsBlurEffect

from PyQt5.QtPrintSupport import *

from PyQt5.QtCore import QUrl
from PyQt5.QtCore import QUrlQuery
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import QSize
from PyQt5.QtCore import QEvent
from PyQt5.QtCore import QPoint

from PyQt5.QtWebEngineWidgets import QWebEnginePage
from PyQt5.QtWebEngineWidgets import QWebEngineDownloadItem
from PyQt5.QtWebEngineWidgets import QWebEngineContextMenuData
from PyQt5.QtWebEngineWidgets import QWebEngineScript
from PyQt5.QtWebChannel import QWebChannel

from PyQt5.QtGui import QKeySequence

from galacteek import log
from galacteek import logUser
from galacteek import ensure
from galacteek import partialEnsure
from galacteek import services
from galacteek.config import cGet
from galacteek.config import configModRegCallback

from galacteek.ipfs.wrappers import *
from galacteek.ipfs import cidhelpers
from galacteek.ipfs import megabytes
from galacteek.ipfs.stat import StatInfo
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ipfs.cidhelpers import joinIpfs
from galacteek.ipfs.cidhelpers import joinIpns
from galacteek.ipfs.cidhelpers import cidValid
from galacteek.core.asynclib import asyncify

from galacteek.browser import greasemonkey
from galacteek.browser.schemes import isSchemeRegistered
from galacteek.browser.schemes import SCHEME_ENS
from galacteek.browser.schemes import SCHEME_IPFS
from galacteek.browser.schemes import SCHEME_IPNS
from galacteek.browser.schemes import SCHEME_DWEB
from galacteek.browser.schemes import SCHEME_HTTP
from galacteek.browser.schemes import SCHEME_HTTPS
from galacteek.browser.schemes import SCHEME_FTP
from galacteek.browser.schemes import SCHEME_Z
from galacteek.browser.schemes import SCHEME_PRONTO_GRAPHS
from galacteek.browser.schemes import DAGProxySchemeHandler
from galacteek.browser.schemes import MultiDAGProxySchemeHandler
from galacteek.browser.schemes import IPFSObjectProxyScheme
from galacteek.browser.schemes import isUrlSupported
from galacteek.browser.schemes import schemeSectionMatch

from galacteek.browser.web3channels import Web3Channel

from galacteek.browser.webprofiles import WP_NAME_IPFS
from galacteek.browser.webprofiles import WP_NAME_MINIMAL
from galacteek.browser.webprofiles import WP_NAME_WEB3
from galacteek.browser.webprofiles import WP_NAME_ANON
from galacteek.browser.webprofiles import webProfilesPrio

from galacteek.dweb.webscripts import scriptFromString
from galacteek.dweb.webscripts import scriptFromQFile
from galacteek.dweb.page import BaseHandler
from galacteek.dweb.page import pyqtSlot
from galacteek.dweb.render import renderTemplate
from galacteek.dweb.htmlparsers import IPFSLinksParser

from galacteek.dweb.channels import dom

from ..pronto import buildProntoGraphsMenu

from .page import BrowserDwebPage
from .urlzone import URLInputWidget
from .graphsearch import ContentSearchResultsTree

from ..forms import ui_browsertab
from ..dag import DAGViewer
from ..helpers import *
from ..dialogs import *
from ..hashmarks import *
from ..i18n import *
from ..colors import *
from ..clipboard import iCopyPathToClipboard
from ..clipboard import iCopyPubGwUrlToClipboard
from ..clipboard import iClipboardEmpty
from ..widgets import *
from ..widgets.overlay import OverlayWidget
from ..clips import *

from galacteek.ui.pinning.pinstatus import PinBatchWidget, PinBatchTab
from galacteek.ui.widgets.pinwidgets import PinObjectButton
from galacteek.ui.widgets.pinwidgets import PinObjectAction
from galacteek.appsettings import *


class CurrentPageHandler(BaseHandler):
    def __init__(self, parent):
        super().__init__(parent)

        self.rootCid = None

    @pyqtSlot()
    def getRootCid(self):
        return self.rootCid


class JSConsoleWidget(QWidget):
    def __init__(self, parent=None):
        super(JSConsoleWidget, self).__init__(parent)

        app = QApplication.instance()

        self.setLayout(QVBoxLayout())

        self.closeButton = QPushButton(iClose())
        self.closeButton.clicked.connect(self.onClose)
        self.textBrowser = QTextBrowser()
        self.layout().addWidget(self.textBrowser)
        self.layout().addWidget(self.closeButton)

        self.hide()
        self.textBrowser.setReadOnly(True)
        self.textBrowser.setAcceptRichText(True)

        self.setObjectName('javascriptConsole')
        self.log('<p><b>Javascript output console</b></p>')

        self.setMinimumSize(
            app.desktopGeometry.width() * 0.6,
            app.desktopGeometry.height() * 0.8,
        )

    def onClose(self):
        self.close()

    def log(self, msg):
        self.textBrowser.append(msg)

    def clear(self):
        self.textBrowser.clear()

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

        self.log('''
           <p>[{level}]
           <b>{source}</b> at line {line}: {message}
           </p>'''.format(
            source=source,
            level=levelH,
            line=lineNumber,
            message=message
        ))


class WebView(IPFSWebView):
    def __init__(self, browserTab, webProfile, parent=None):
        super(WebView, self).__init__(parent=parent)

        self.app = QCoreApplication.instance()
        self.browserTab = browserTab
        self.linkInfoTimer = QTimer()
        self.linkInfoTimer.timeout.connect(self.onLinkInfoTimeout)
        self.setMouseTracking(True)

        self.pageLoading = False

        self.webPage = None
        self.altSearchPage = None

        self.changeWebProfile(webProfile)

    def resizeEvent(self, event):
        for child in self.children():
            if isinstance(child, OverlayWidget):
                child.resize(event.size())

        super().resizeEvent(event)

    def blur(self) -> None:
        """
        Apply a blur graphics effect on this webengine view
        """

        if self.graphicsEffect() is not None:
            return

        blurEffect = QGraphicsBlurEffect(self)
        blurEffect.setBlurHints(QGraphicsBlurEffect.PerformanceHint)
        blurEffect.setBlurRadius(2)

        self.setGraphicsEffect(blurEffect)

    def noGraphicsEffect(self):
        """
        Remove any graphics effect on this webengine view
        """
        self.setGraphicsEffect(None)

    def web3ChangeChannel(self, channel: Web3Channel):
        self.installDefaultPage(web3Channel=channel)

    def createWindow(self, wintype):
        log.debug('createWindow called, wintype: {}'.format(wintype))

        if wintype == QWebEnginePage.WebBrowserTab:
            tab = self.app.mainWindow.addBrowserTab(
                current=True,
                position='nextcurrent'
            )
            return tab.webEngineView

    def onViewSource(self):
        def callback(html):
            if not html:
                return

            if self.browserTab.currentIpfsObject:
                tooltip = str(self.browserTab.currentIpfsObject)
            else:
                tooltip = self.page().url().toString()

            tab = GalacteekTab(self.app.mainWindow)
            widget = PageSourceWidget(tab)
            ensure(widget.showSource(html))
            tab.addToLayout(widget)
            self.app.mainWindow.registerTab(
                tab, 'Page source',
                current=True,
                icon=getMimeIcon('text/html'),
                tooltip=tooltip)

        self.page().toHtml(callback)

    def onJsMessage(self, level, message, lineNo, sourceId):
        self.browserTab.jsConsole.showMessage(level, message, lineNo, sourceId)

    def onLinkInfoTimeout(self):
        self.browserTab.hoveredUrlTimeout()

    def onFollowTheAtom(self, path):
        log.debug('Following atom feed: {}'.format(path))
        ensure(self.app.mainWindow.atomButton.atomFeedSubscribe(str(path)))

    def onLinkHovered(self, urlString):
        if not isinstance(urlString, str):
            return

        url = QUrl(urlString)
        if not url.isValid():
            return

        if url.isRelative() and self.browserTab.currentIpfsObject:
            ipfsPath = self.browserTab.currentIpfsObject.child(
                url.toString())
        else:
            ipfsPath = IPFSPath(urlString)

        if ipfsPath.valid:
            self.browserTab.displayHoveredUrl(ipfsPath.asQtUrl)
        else:
            self.browserTab.displayHoveredUrl(url)

        self.linkInfoTimer.start(2000)

    def contextMenuCreateDefault(self):
        """
        Default context menu (returned for non-link rclicks)
        """
        menu = QMenu(self)
        menu.addAction(self.pageAction(QWebEnginePage.Back))
        menu.addAction(self.pageAction(QWebEnginePage.Forward))
        menu.addSeparator()
        menu.addAction(self.pageAction(QWebEnginePage.Reload))
        menu.addAction(self.pageAction(QWebEnginePage.ReloadAndBypassCache))
        menu.addSeparator()
        menu.addAction(self.pageAction(QWebEnginePage.Cut))
        menu.addAction(self.pageAction(QWebEnginePage.Copy))
        menu.addSeparator()
        menu.addAction(self.pageAction(QWebEnginePage.ViewSource))
        return menu

    def contextMenuEvent(self, event):
        # TODO: cleanup and refactoring

        analyzer = self.app.rscAnalyzer
        currentPage = self.page()
        contextMenuData = currentPage.contextMenuData()

        urlDecoded = QUrl.fromPercentEncoding(
            contextMenuData.linkUrl().toEncoded())
        url = QUrl(urlDecoded)

        mediaType = contextMenuData.mediaType()
        mediaUrlDecoded = QUrl.fromPercentEncoding(
            contextMenuData.mediaUrl().toEncoded())
        mediaUrl = QUrl(mediaUrlDecoded)

        log.debug('Context URL: {0}'.format(url.toString()))

        if not url.isValid() and not mediaUrl.isValid():
            selectedText = self.webPage.selectedText()

            if selectedText:
                menu = self.contextMenuCreateDefault()
                menu.addSeparator()
                menu.addAction(iSaveSelectedText(), self.onSaveSelection)
                menu.exec(event.globalPos())
                return

            menu = self.contextMenuCreateDefault()
            menu.exec(event.globalPos())
            return

        ipfsPath = IPFSPath(url.toString(), autoCidConv=True)

        if mediaType != QWebEngineContextMenuData.MediaTypeNone and mediaUrl:
            mediaIpfsPath = IPFSPath(mediaUrl.toString(), autoCidConv=True)
        else:
            mediaIpfsPath = None

        if ipfsPath.valid:

            menu = QMenu(self)
            menu.addAction(getIcon('clipboard.png'),
                           iCopyPathToClipboard(),
                           functools.partial(self.app.setClipboardText,
                                             str(ipfsPath)
                                             ))
            menu.addAction(getIcon('clipboard.png'),
                           iCopyPubGwUrlToClipboard(),
                           functools.partial(self.app.setClipboardText,
                                             ipfsPath.publicGwUrl
                                             ))
            menu.addSeparator()
            menu.addAction(getIcon('open.png'), iOpen(), functools.partial(
                ensure, self.app.resourceOpener.open(ipfsPath)))
            menu.addAction(getIcon('ipfs-logo-128-black.png'),
                           iOpenLinkInTab(),
                           functools.partial(self.openInTab, ipfsPath))
            menu.addAction(getIcon('ipfs-logo-128-black.png'),
                           iOpenLinkInBgTab(),
                           functools.partial(self.openInTab, ipfsPath, False))
            menu.addSeparator()
            menu.addAction(getIcon('hashmarks.png'),
                           iHashmark(),
                           functools.partial(self.hashmarkPath, str(ipfsPath)))
            menu.addSeparator()

            pinObjectAction = PinObjectAction(ipfsPath, parent=menu)

            menu.addSeparator()
            menu.addAction(pinObjectAction)

            def rscAnalyzed(path: str, iMenu, fut: asyncio.Future):
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
                            functools.partial(self.onFollowTheAtom, path)
                        )
            ensure(
                analyzer(ipfsPath),
                futcallback=functools.partial(
                    rscAnalyzed,
                    ipfsPath,
                    menu
                )
            )

            menu.exec(event.globalPos())

        elif mediaIpfsPath and mediaIpfsPath.valid:
            # Needs refactor
            menu = QMenu(self)

            menu.addSeparator()
            menu.addAction(getIcon('clipboard.png'),
                           iCopyPathToClipboard(),
                           functools.partial(self.app.setClipboardText,
                                             str(mediaIpfsPath)
                                             ))
            menu.addAction(getIcon('clipboard.png'),
                           iCopyPubGwUrlToClipboard(),
                           functools.partial(self.app.setClipboardText,
                                             mediaIpfsPath.publicGwUrl
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
            menu.addSeparator()
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
                futcallback=functools.partial(
                    rscAnalyzed,
                    mediaIpfsPath,
                    mediaType,
                    analyzer
                )
            )

            menu.exec(event.globalPos())
        else:
            # Non-IPFS URL

            menu = QMenu(self)

            if isUrlSupported(url):
                # Non-IPFS URL but a scheme we know
                menu.addAction(
                    iOpenLinkInTab(),
                    functools.partial(self.openUrlInTab, url, True)
                )
                menu.addAction(
                    iOpenLinkInBgTab(),
                    functools.partial(self.openUrlInTab, url, False)
                )

            menu.exec(event.globalPos())

    @asyncify
    async def onSaveSelection(self):
        selectedText = self.webPage.selectedText()

        if selectedText:
            await self.saveSelectedText(selectedText)

    @ipfsOp
    async def saveSelectedText(self, ipfsop, rawText):
        try:
            entry = await ipfsop.addString(rawText)
        except Exception:
            pass
        else:
            self.app.setClipboardText(entry['Hash'])

    def hashmarkPath(self, path):
        ipfsPath = IPFSPath(path, autoCidConv=True)
        if ipfsPath.valid:
            ensure(addHashmarkAsync(
                ipfsPath.fullPath,
                title=ipfsPath.basename if ipfsPath.basename else
                iUnknown()))

    def openInTab(self, path, current=True):
        tab = self.browserTab.gWindow.addBrowserTab(
            position='nextcurrent',
            current=current
        )
        tab.browseFsPath(path)

    def openUrlInTab(self, url, switch=False):
        tab = self.browserTab.gWindow.addBrowserTab(
            position='nextcurrent',
            current=switch
        )
        tab.enterUrl(url)

    def downloadLink(self, menudata):
        url = menudata.linkUrl()
        self.page().download(url, None)

    def installDefaultPage(self, web3Channel: Web3Channel = None):
        if self.webPage:
            self.webPage.deleteLater()

        self.webPage = BrowserDwebPage(self.webProfile, self.browserTab)
        self.webPage.jsConsoleMessage.connect(self.onJsMessage)
        self.webPage.linkHovered.connect(self.onLinkHovered)

        if web3Channel:
            self.webPage.changeWebChannel(web3Channel)
        else:
            # Default channel with autofill
            channel = QWebChannel(self)
            channel.registerObject('dombridge',
                                   dom.DOMBridge(self))
            self.webPage.changeWebChannel(channel)

        self.setPage(self.webPage)

    async def setSearchPage(self):
        if not self.altSearchPage:
            self.altSearchPage = \
                self.app.mainWindow.ipfsSearchPageFactory.getPage(
                    searchMode='nocontrols')
            await self.altSearchPage.eventRendered.wait()

        self.setPage(self.altSearchPage)
        return self.altSearchPage

    def setBrowserPage(self):
        if not self.webPage:
            self.installDefaultPage()
        else:
            self.setPage(self.webPage)

    def changeWebProfile(self, profile):
        self.webProfile = profile
        self.installDefaultPage()


class BrowserKeyFilter(QObject):
    hashmarkPressed = pyqtSignal()
    savePagePressed = pyqtSignal()
    reloadPressed = pyqtSignal()
    reloadFullPressed = pyqtSignal()
    zoominPressed = pyqtSignal()
    zoomoutPressed = pyqtSignal()
    focusUrlPressed = pyqtSignal()
    findInPagePressed = pyqtSignal()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            modifiers = event.modifiers()
            key = event.key()

            if modifiers & Qt.ControlModifier:
                if key == Qt.Key_B:
                    self.hashmarkPressed.emit()
                    return True
                if key == Qt.Key_R:
                    self.reloadPressed.emit()
                    return True
                if key == Qt.Key_F5:
                    self.reloadFullPressed.emit()
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
                if key == Qt.Key_F:
                    self.findInPagePressed.emit()
                    return True

            if key == Qt.Key_F5:
                self.reloadPressed.emit()
                return True

        return False


class CurrentObjectController(PopupToolButton):
    objectVisited = pyqtSignal(IPFSPath)

    dagViewRequested = pyqtSignal(IPFSPath)

    def __init__(self, parent=None):
        super(CurrentObjectController, self).__init__(
            mode=QToolButton.InstantPopup, parent=parent)

        self.app = QApplication.instance()

        self.currentPath = None
        self.objectVisited.connect(self.onVisited)

        self.pathCubeOrange = ':/share/icons/cube-orange.png'
        self.pathCubeBlue = ':/share/icons/cube-blue.png'

        self.setIcon(getIcon('cube-orange.png'))
        self.setAutoRaise(True)

        self.exploreDirectoryAction = QAction(
            getIcon('folder-open.png'),
            iExploreDirectory(),
            self,
            triggered=self.onExploreDirectory)
        self.dagViewAction = QAction(getIcon('ipld.png'),
                                     iDagView(), self,
                                     triggered=self.onDAGView)
        self.parentDagViewAction = QAction(getIcon('ipld.png'),
                                           iParentDagView(), self,
                                           triggered=self.onParentDAGView)
        self.qaLinkAction = QAction(getIconIpfsWhite(),
                                    iLinkToQaToolbar(), self,
                                    triggered=self.onQaLink)
        self.copyCurPathAction = QAction(getIcon('clipboard.png'),
                                         iCopyPathToClipboard(), self,
                                         triggered=self.onCopyPathToCb)
        self.hashmarkRootCidAction = QAction(getIcon('hashmark-black.png'),
                                             iHashmarkRootObject(), self,
                                             triggered=self.onHashmarkRoot)
        self.hashmarkObjectAction = QAction(getIcon('hashmark-black.png'),
                                            iHashmarkThisPage(), self,
                                            triggered=self.onHashmarkThisPage)

        self.setDefaultAction(self.dagViewAction)

        self.menu.addAction(self.exploreDirectoryAction)
        self.menu.addSeparator()
        self.menu.addAction(self.copyCurPathAction)
        self.menu.addSeparator()
        self.menu.addAction(self.qaLinkAction)
        self.menu.addSeparator()
        self.menu.addAction(self.dagViewAction)
        self.menu.addSeparator()
        self.menu.addAction(self.parentDagViewAction)
        self.menu.addSeparator()
        self.menu.addAction(self.hashmarkRootCidAction)
        self.menu.addSeparator()
        self.menu.addAction(self.hashmarkObjectAction)
        self.menu.addSeparator()

        self.setIconSize(QSize(24, 24))

    def onQaLink(self):
        if self.currentPath and self.currentPath.valid:
            toolbar = self.app.mainWindow.toolbarQa

            toolbar.ipfsObjectDropped.emit(self.currentPath)

    def onExploreDirectory(self):
        if self.currentPath and self.currentPath.valid:
            self.app.mainWindow.explore(self.currentPath.objPath)

    def onDAGView(self):
        if self.currentPath and self.currentPath.valid:
            self.dagViewRequested.emit(self.currentPath)

    def onParentDAGView(self):
        if self.currentPath and self.currentPath.valid:
            self.dagViewRequested.emit(self.currentPath.parent())

    def onCopyPathToCb(self):
        if self.currentPath and self.currentPath.valid:
            self.app.setClipboardText(str(self.currentPath))

    def onHashmarkThisPage(self):
        if self.currentPath and self.currentPath.valid:
            ensure(addHashmarkAsync(self.currentPath.fullPath))

    def onHashmarkRoot(self):
        if self.currentPath and self.currentPath.valid:
            if self.currentPath.isIpfs:
                rootCidPath = joinIpfs(self.currentPath.rootCidRepr)
                ensure(addHashmarkAsync(
                    rootCidPath,
                    title=rootCidPath))
            elif self.currentPath.isIpns:
                root = self.currentPath.root()
                if not root:
                    return messageBox(
                        iInvalidObjectPath(str(self.currentPath)))

                ensure(addHashmarkAsync(
                    str(root), str(root)))

    def onVisited(self, ipfsPath):
        ensure(self.displayObjectInfos(ipfsPath))

    @ipfsOp
    async def displayObjectInfos(self, ipfsop, ipfsPath):
        self.currentPath = ipfsPath

        self.parentDagViewAction.setEnabled(
            self.currentPath.subPath is not None)

        objCid = None
        cidRepr = ipfsPath.rootCidRepr

        if ipfsPath.isIpfs:
            # First generic tooltip without resolved CID
            self.setToolTip(iCidTooltipMessage(
                self.pathCubeBlue,
                ipfsPath.rootCid.version, '',
                cidRepr,
                iUnknown()
            ))

            objCid = await ipfsPath.resolve(ipfsop, timeout=5)

        if self.currentPath != ipfsPath:
            # Current object has changed while resolving, let the new
            # object's tooltip appear
            return

        if ipfsPath.rootCidUseB32:
            self.setIcon(getIcon('cube-orange.png'))

            self.setToolTip(iCidTooltipMessage(
                self.pathCubeOrange,
                1, '(base32)',
                cidRepr,
                objCid if objCid else iUnknown()
            ))
        else:
            self.setIcon(getIcon('cube-blue.png'))

            if ipfsPath.rootCid:
                self.setToolTip(iCidTooltipMessage(
                    self.pathCubeBlue,
                    ipfsPath.rootCid.version, '',
                    cidRepr,
                    objCid if objCid else iUnknown()
                ))

            elif ipfsPath.isIpns:
                self.setToolTip(
                    iIpnsTooltipMessage(
                        self.pathCubeBlue,
                        ipfsPath.ipnsFqdn if ipfsPath.ipnsFqdn else
                        ipfsPath.ipnsKey
                    )
                )


class BrowserLoadingWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.vl = QVBoxLayout(self)
        self.setLayout(self.vl)

        self.animation = AnimatedLabel(BouncyOrbitClip(),
                                       parent=self)
        self.vl.addWidget(self.animation, 1, Qt.AlignCenter)

    def loading(self, progress: int = 100):
        self.animation.startClip()
        self.animation.clip.setSpeed(max(progress, 100))

    def hideEvent(self, ev):
        self.animation.stopClip()


class PageResourceNotLoadingWidget(OverlayWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.animation = AnimatedLabel(BouncyOrbitClip(),
                                       parent=self)
        if parent:
            self.resize(parent.size())

        self.loading()

    def loading(self, progress: int = 100):
        self.animation.startClip()


class BrowserTab(GalacteekTab):
    # signals
    ipfsObjectVisited = pyqtSignal(IPFSPath)

    resolveTimerEnsMs = 7000

    def __init__(self, gWindow, minProfile=None, pinBrowsed=False,
                 parent=None):
        super(BrowserTab, self).__init__(gWindow, parent=parent)

        self.urlInput = None

        self.browserWidget = QWidget(parent=self)
        self.browserWidget.setAttribute(Qt.WA_DeleteOnClose)

        self.jsConsoleWidget = JSConsoleWidget()

        self.ui = ui_browsertab.Ui_BrowserTabForm()
        self.ui.setupUi(self.browserWidget)

        self.vLayout.addWidget(self.browserWidget)

        # Content search tree
        self.historySearches = ContentSearchResultsTree(parent=self)
        self.historySearches.hide()

        self.urlZone = URLInputWidget(
            self.history, self.historySearches, self,
            parent=self.browserWidget
        )
        self.ui.layoutUrl.addWidget(self.urlZone)

        # Search
        self.ui.searchInPage.returnPressed.connect(self.onSearchInPage)
        self.ui.searchInPage.textEdited.connect(self.onSearchInPageEdit)
        self.ui.searchPrev.clicked.connect(self.onSearchInPagePrev)
        self.ui.searchNext.clicked.connect(self.onSearchInPageNext)
        self.ui.searchButton.clicked.connect(self.onSearchInPage)
        self.ui.searchCancel.clicked.connect(self.onSearchCancel)
        self.ui.findToolButton.setCheckable(True)
        self.ui.findToolButton.toggled.connect(self.searchControlsSetVisible)

        # Current object controller
        self.curObjectCtrl = CurrentObjectController(self)
        self.curObjectCtrl.dagViewRequested.connect(self.onDagViewRequested)
        self.curObjectCtrl.hide()
        self.ui.layoutObjectInfo.addWidget(self.curObjectCtrl)

        initialProfileName = cGet('defaultWebProfile',
                                  mod='galacteek.browser.webprofiles')
        if initialProfileName not in self.app.availableWebProfilesNames():
            initialProfileName = WP_NAME_MINIMAL

        # Use a 'minimum' web profile if requested
        if isinstance(minProfile, str):
            minProfilePrio = webProfilesPrio.get(minProfile, 0)
            initProfilePrio = webProfilesPrio.get(initialProfileName, 0)

            if minProfilePrio > initProfilePrio:
                log.debug('Using requested minimum web profile: {p}'.format(
                    p=minProfile))
                initialProfileName = minProfile

        webProfile = self.getWebProfileByName(initialProfileName)

        self.webEngineView = WebView(
            self, webProfile,
            parent=self.stack
        )

        self.webLoadingWidget = BrowserLoadingWidget(parent=self.stack)

        self.stack.addWidget(self.webLoadingWidget)
        self.stack.addWidget(self.webEngineView)

        self.stackShowWebEngine()

        self.webEngineView.urlChanged.connect(self.onUrlChanged)
        self.webEngineView.loadFinished.connect(self.onLoadFinished)
        self.webEngineView.iconChanged.connect(
            partialEnsure(self.onIconChanged))
        self.webEngineView.loadStarted.connect(self.onLoadStarted)
        self.webEngineView.loadProgress.connect(self.onLoadProgress)
        self.webEngineView.titleChanged.connect(self.onTitleChanged)

        self.ui.backButton.clicked.connect(self.backButtonClicked)
        self.ui.forwardButton.clicked.connect(self.forwardButtonClicked)

        self.ui.reloadPageButton.clicked.connect(self.refreshButtonClicked)
        self.ui.stopButton.clicked.connect(self.stopButtonClicked)

        self.ui.backButton.setEnabled(False)
        self.ui.forwardButton.setEnabled(False)
        self.ui.backButton.setVisible(True)
        self.ui.forwardButton.setVisible(True)

        self.ui.stopButton.setEnabled(False)
        self.ui.reloadPageButton.hide()
        self.ui.stopButton.hide()

        # Page ops button
        self.createPageOpsButton()

        self.hashmarkPageAction = QAction(
            getIcon('hashmark-black.png'),
            iHashmarkThisPage(),
            self,
            shortcut=QKeySequence('Ctrl+b'),
            triggered=partialEnsure(self.onHashmarkPage)
        )
        self.hashmarkButton = QToolButton()
        self.hashmarkButton.setIcon(getIcon('hashmark-black.png'))
        self.hashmarkButton.clicked.connect(partialEnsure(self.onHashmarkPage))
        self.hashmarkButton.setEnabled(False)

        self.hashmarkWAction = QWidgetAction(self)
        self.hashmarkWAction.setDefaultWidget(self.hashmarkButton)
        self.hashmarkWAction.setEnabled(False)

        # Setup the IPFS control tool button (has actions
        # for browsing CIDS and web profiles etc..)

        self.prontoGraphsMenu = buildProntoGraphsMenu()
        self.prontoGraphsMenu.triggered.connect(self.onViewProntoGraph)

        self.ipfsControlMenu = QMenu(self)
        self.webProfilesMenu = QMenu('Web profile', self.ipfsControlMenu)

        self.webProfilesGroup = QActionGroup(self.webProfilesMenu)
        self.webProfilesGroup.setExclusive(True)
        self.webProfilesGroup.triggered.connect(self.onWebProfileSelected)

        self.webProAnonAction = QAction(WP_NAME_ANON, self)
        self.webProAnonAction.setCheckable(True)
        self.webProMinAction = QAction(WP_NAME_MINIMAL, self)
        self.webProMinAction.setCheckable(True)
        self.webProIpfsAction = QAction(WP_NAME_IPFS, self)
        self.webProIpfsAction.setCheckable(True)
        self.webProWeb3Action = QAction(WP_NAME_WEB3, self)
        self.webProWeb3Action.setCheckable(True)

        self.webProfilesGroup.addAction(self.webProAnonAction)
        self.webProfilesGroup.addAction(self.webProMinAction)
        self.webProfilesGroup.addAction(self.webProIpfsAction)
        self.webProfilesGroup.addAction(self.webProWeb3Action)

        for action in self.webProfilesGroup.actions():
            self.webProfilesMenu.addAction(action)

        self.checkWebProfileByName(initialProfileName)

        self.ui.webProfileSelector.setMenu(self.webProfilesMenu)

        self.browserHelpAction = QAction(getIcon('help.png'),
                                         iHelp(), self,
                                         triggered=self.onShowBrowserHelp)
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
                                        iFollowIpns(), self,
                                        triggered=self.onFollowIpns)
        self.loadHomeAction = QAction(getIcon('go-home.png'),
                                      iBrowseHomePage(), self,
                                      triggered=self.onLoadHome)

        self.jsConsoleAction = QAction(getIcon('terminal.png'),
                                       iJsConsole(), self,
                                       shortcut=QKeySequence('Ctrl+j'),
                                       triggered=self.onJsConsoleToggle)

        self.mapPathAction = QAction(
            getIconIpfsIce(),
            iCreateQaMapping(),
            self,
            triggered=partialEnsure(
                self.onCreateMapping))

        self.loadFromCbAction = QAction(
            getIcon('clipboard.png'),
            iBrowseCurrentClipItem(), self,
            triggered=self.onBrowseCurrentClipItem
        )

        self.followIpnsAction.setEnabled(False)

        self.ipfsControlMenu.addAction(self.browserHelpAction)
        self.ipfsControlMenu.addSeparator()
        # self.ipfsControlMenu.addMenu(self.webProfilesMenu)
        # self.ipfsControlMenu.addSeparator()

        self.ipfsControlMenu.addMenu(self.pageOpsButton.menu)
        self.ipfsControlMenu.addSeparator()

        self.ipfsControlMenu.addAction(self.jsConsoleAction)
        self.ipfsControlMenu.addSeparator()
        self.ipfsControlMenu.addAction(self.mapPathAction)
        self.ipfsControlMenu.addSeparator()
        self.ipfsControlMenu.addAction(self.loadFromCbAction)
        self.ipfsControlMenu.addAction(self.loadIpfsCIDAction)
        self.ipfsControlMenu.addAction(self.loadIpfsMultipleCIDAction)
        self.ipfsControlMenu.addAction(self.loadIpnsAction)
        self.ipfsControlMenu.addAction(self.followIpnsAction)
        self.ipfsControlMenu.addAction(self.loadHomeAction)

        self.ipfsControlMenu.addSeparator()
        self.ipfsControlMenu.addMenu(self.prontoGraphsMenu)

        self.controller = PopupToolButton(
            getIcon('cube-blue.png'),
            mode=QToolButton.InstantPopup
        )
        self.controller.setMenu(self.ipfsControlMenu)
        self.controller.setPopupMode(QToolButton.InstantPopup)
        self.controller.clicked.connect(self.onLoadIpfsCID)

        self.controllerWAction = QWidgetAction(self)
        self.controllerWAction.setDefaultWidget(self.controller)

        self.ui.pBarBrowser.setTextVisible(False)
        self.ui.pinAllButton.setCheckable(True)
        self.ui.pinAllButton.setAutoRaise(True)

        self.ui.contentDetailsLabel.setVisible(False)

        if pinBrowsed:
            self.ui.pinAllButton.setChecked(True)
        else:
            self.ui.pinAllButton.setChecked(self.gWindow.pinAllGlobalChecked)

        self.ui.pinAllButton.toggled.connect(self.onToggledPinAll)

        # PIN tool button
        self.pinToolButton = PinObjectButton(
            mode=QToolButton.InstantPopup
        )
        self.pinToolButton.pinQueueName = 'browser'
        self.pinToolButton.mode = 'web'
        self.pinToolButton.sPinPageLinksRequested.connectTo(
            self.onPinPageLinks)

        self.pinWAction = QWidgetAction(self)
        self.pinWAction.setDefaultWidget(self.pinToolButton)

        self.ui.zoomInButton.clicked.connect(self.onZoomIn)
        self.ui.zoomOutButton.clicked.connect(self.onZoomOut)

        self.ui.zoomInButton.hide()
        self.ui.zoomOutButton.hide()

        # Event filter
        evfilter = BrowserKeyFilter(self)
        evfilter.hashmarkPressed.connect(partialEnsure(self.onHashmarkPage))
        evfilter.reloadPressed.connect(self.onReloadPage)
        evfilter.reloadFullPressed.connect(self.onReloadPageNoCache)
        evfilter.zoominPressed.connect(self.onZoomIn)
        evfilter.zoomoutPressed.connect(self.onZoomOut)
        evfilter.focusUrlPressed.connect(self.onFocusUrl)
        evfilter.findInPagePressed.connect(self.onToggleSearchControls)
        self.installEventFilter(evfilter)

        self.resolveTimer = QTimer(self)

        self.searchControlsSetVisible(False)

        self.app.clipTracker.clipboardPathProcessed.connect(
            self.onClipboardIpfs)
        self.ipfsObjectVisited.connect(self.onPathVisited)

        self._currentIpfsObject = None
        self._currentUrl = None
        self.currentPageTitle = None

        # Bind tab signals
        self.tabVisibilityChanged.connect(self.onTabVisibility)

        self.configApply()
        configModRegCallback(self.onModuleConfigChanged)

    @property
    def prontoService(self):
        return services.getByDotName('ld.pronto')

    @property
    def history(self):
        return self.gWindow.app.urlHistory

    @property
    def stack(self):
        return self.ui.browserContentStack

    @property
    def webView(self):
        return self.webEngineView

    @property
    def currentUrl(self):
        return self._currentUrl

    @property
    def currentUrlHasFileName(self):
        if self.currentUrl:
            return self.currentUrl.fileName() != ''

    @property
    def jsConsole(self):
        return self.jsConsoleWidget

    @property
    def tabPage(self):
        return self.workspace.tabWidget.widget(self.tabPageIdx)

    @property
    def tabPageIdx(self):
        return self.workspace.tabWidget.indexOf(self)

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
    def currentIpfsObject(self):
        return self._currentIpfsObject

    def tabActions(self) -> list:
        """
        Return a list of widget actions for this browser tab

        - main controller
        - pin action
        - hashmark action
        """
        return [
            self.controllerWAction,
            self.pinWAction,
            self.hashmarkWAction
        ]

    def tabDestroyedPost(self):
        # Reparent

        self.webEngineView.deleteLater()

        self.urlZone.setParent(None)
        self.urlZone.deleteLater()
        self.browserWidget.setParent(None)
        self.browserWidget.deleteLater()

    def stackShowWebEngine(self):
        self.stack.setCurrentWidget(self.webEngineView)

    def stackShowLoading(self):
        self.stack.setCurrentWidget(self.webLoadingWidget)
        self.webLoadingWidget.loading(0)

    def configApply(self):
        zoom = cGet('zoom.default')
        self.setZoomPercentage(zoom)

    def onModuleConfigChanged(self):
        self.configApply()

    def onTabVisibility(self, visible):
        if not visible:
            self.urlZone.hideMatches()

        self.urlZone.startStopUrlAnimation(visible)

    def hoveredUrlTimeout(self):
        self.ui.contentDetailsLabel.setVisible(False)

    def displayHoveredUrl(self, url: QUrl):
        wegeom = self.webEngineView.geometry()
        wegp = self.webEngineView.mapToGlobal(QPoint(0, 0))

        if isUrlSupported(url):
            urls = url.toString()

            if len(urls) > 92:
                urls = urls[0:92] + '...'

            easyToolTip(
                urls,
                QPoint(wegp.x(), wegp.y() + wegeom.height() - 32),
                self.webEngineView,
                5000,
                1.5
            )

            self.urlZone.pageUrlHovered.emit(url)

    async def onTabDoubleClicked(self):
        log.debug('Browser Tab double clicked')
        return True

    def focusOutEvent(self, event):
        self.urlZone.hideMatches()
        super().focusOutEvent(event)

    def showEvent(self, event):
        if not self.currentUrl:
            self.focusUrlZone(True)

        super().showEvent(event)

    def fromGateway(self, authority):
        return authority.endswith(self.gatewayAuthority) or \
            authority.endswith('ipfs.' + self.gatewayAuthority)

    def createPageOpsButton(self):
        icon = getMimeIcon('text/html')
        iconPrinter = getIcon('printer.png')

        self.pageOpsButton = PopupToolButton(
            icon, mode=QToolButton.InstantPopup, parent=None
        )
        self.pageOpsButton.setAutoRaise(True)
        self.pageOpsButton.menu.setTitle('Page')
        self.pageOpsButton.menu.setIcon(icon)
        self.pageOpsButton.menu.addAction(
            icon, iSaveContainedWebPage(), self.onSavePageContained)
        self.pageOpsButton.menu.addAction(
            icon, iSaveWebPageToPdfFile(), self.onSavePageToPdf)
        self.pageOpsButton.menu.addSeparator()
        self.pageOpsButton.menu.addAction(
            iconPrinter, iPrintWebPageText(), self.onPrintWebPage)
        self.pageOpsButton.menu.addSeparator()

        ensure(self.createPageOpsMfsMenu())

    @ipfsOp
    async def createPageOpsMfsMenu(self, ipfsop):
        if not ipfsop.ctx.currentProfile:
            return

        self.mfsMenu = ipfsop.ctx.currentProfile.createMfsMenu(
            title=iLinkToMfsFolder(), parent=self
        )
        self.mfsMenu.setIcon(getIcon('folder-open-black.png'))
        self.mfsMenu.triggered.connect(self.onMoveToMfsMenuTriggered)
        self.pageOpsButton.menu.addSeparator()
        self.pageOpsButton.menu.addMenu(self.mfsMenu)

    def onMoveToMfsMenuTriggered(self, action):
        mfsItem = action.data()

        if not mfsItem:
            return

        if not self.currentIpfsObject:
            # ERR
            return

        cTitle = self.currentPageTitle if self.currentPageTitle else ''

        ensure(runDialogAsync(
            TitleInputDialog, cTitle,
            accepted=functools.partial(
                self.onMoveToMfsWithTitle,
                self.currentIpfsObject,
                mfsItem
            )
        ))

    def onMoveToMfsWithTitle(self, ipfsPath, mfsItem, dialog):
        cTitle = dialog.tEdit.text().replace('/', '_')
        if not cTitle:
            return messageBox('Invalid title')

        ensure(self.linkPageToMfs(ipfsPath, mfsItem, cTitle))

    @ipfsOp
    async def linkPageToMfs(self, ipfsop, ipfsPath, mfsItem, cTitle):
        basename = ipfsPath.basename

        dest = os.path.join(mfsItem.path, cTitle.strip())

        if basename and not (ipfsPath.isIpfsRoot or ipfsPath.isIpnsRoot):
            await ipfsop.filesMkdir(dest)
            dest = os.path.join(dest, basename)

        try:
            await ipfsop.client.files.cp(
                ipfsPath.objPath,
                dest
            )
        except aioipfs.APIError:
            messageBox('Error while linking')

        self.pinPath(ipfsPath.objPath, recursive=True, notify=True)

    def installCustomPageScripts(self, handler, url):
        # Page-specific IPFS scripts

        if url.scheme() == SCHEME_IPFS:
            rootCid = None

            if issubclass(handler.__class__, DAGProxySchemeHandler):
                if handler.proxied:
                    rootCid = handler.proxied.dagCid
            elif issubclass(handler.__class__, MultiDAGProxySchemeHandler):
                if len(handler.proxied) > 0:
                    rootCid = handler.proxied[0].dagCid
            else:
                rootCid = url.host()

            if not rootCid:
                return

            scripts = self.webEngineView.webPage.scripts()

            script = scriptFromString('rootcid', '''
                window.rootcid = '{cid}';
            '''.format(cid=rootCid))

            existing = scripts.findScript('rootcid')
            if existing.isNull():
                scripts.remove(existing)

            scripts.insert(script)

    async def installGreaseMonkeyScripts(self, handler, url):
        # Chimpanzee that

        pageScripts = self.webEngineView.webPage.scripts()

        if not greasemonkey.gm_manager:
            return

        for gms in greasemonkey.gm_manager.all_scripts():
            fn = gms.full_name()

            if not pageScripts.findScript(fn).isNull():
                continue

            script = QWebEngineScript()
            script.setRunsOnSubFrames(gms.runs_on_sub_frames)
            script.setInjectionPoint(QWebEngineScript.DocumentReady)
            script.setSourceCode(await gms.code())
            script.setName(fn)

            try:
                world = int(gms.jsworld)
                script.setWorldId(world)
            except ValueError:
                pass

            if gms.needs_document_end_workaround():
                script.setInjectionPoint(QWebEngineScript.DocumentReady)

            pageScripts.insert(script)

    def onDagViewRequested(self, ipfsPath):
        view = DAGViewer(ipfsPath.objPath, self.app.mainWindow)
        self.app.mainWindow.registerTab(
            view, iDagViewer(),
            current=True,
            icon=getIcon('ipld.png'),
            tooltip=str(ipfsPath)
        )

    def onPathVisited(self, ipfsPath):
        # Called after a new IPFS object has been loaded in this tab

        if ipfsPath.valid:
            self.curObjectCtrl.objectVisited.emit(ipfsPath)
            ensure(self.tsVisitPath(ipfsPath.objPath))

    @ipfsStatOp
    async def tsVisitPath(self, ipfsop, path, stat):
        # If automatic pinning is checked we pin the object
        if self.pinAll is True:
            self.pinPath(path, recursive=False, notify=False)

    def changeWebProfileByName(self, wpName):
        if self.webEngineView.webProfile.profileName == wpName:
            log.debug('Profile {p} already set'.format(p=wpName))
            return

        self.checkWebProfileByName(wpName)

    def checkWebProfileByName(self, wpName):
        if wpName == WP_NAME_MINIMAL:
            self.webProMinAction.setChecked(True)
        if wpName == WP_NAME_ANON:
            self.webProAnonAction.setChecked(True)
        elif wpName == WP_NAME_IPFS:
            self.webProIpfsAction.setChecked(True)
        elif wpName == WP_NAME_WEB3:
            self.webProWeb3Action.setChecked(True)

    def getWebProfileByName(self, wpName, fallback=WP_NAME_MINIMAL):
        return self.app.webProfiles.get(
            wpName, self.app.webProfiles[fallback])

    def onWebProfileSelected(self, action):
        if self.webEngineView.webProfile.profileName == action.text():
            log.debug('Profile {p} already set'.format(p=action.text()))
            return

        url = self.currentUrl

        if action is self.webProMinAction:
            self.webEngineView.changeWebProfile(
                self.getWebProfileByName(WP_NAME_MINIMAL)
            )
        elif action is self.webProIpfsAction:
            self.webEngineView.changeWebProfile(
                self.getWebProfileByName(WP_NAME_IPFS)
            )
        elif action is self.webProAnonAction:
            self.webEngineView.changeWebProfile(
                self.getWebProfileByName(WP_NAME_ANON)
            )
        elif action is self.webProWeb3Action:
            self.webEngineView.changeWebProfile(
                self.getWebProfileByName(WP_NAME_WEB3)
            )

        if url:
            # Reload page
            self.enterUrl(url)
        else:
            async def showProfileChangedPage():
                pName = self.webEngineView.webProfile.profileName
                body = await renderTemplate(
                    'profilechanged.html',
                    webProfile=pName,
                    title='Web profile changed to {name}'.format(name=pName)
                )
                self.webEngineView.webPage.setHtml(
                    body, QUrl('z:/profilechanged.html'))

            ensure(showProfileChangedPage())

    def onShowBrowserHelp(self):
        self.enterUrl(QUrl('manual:/browsing.html'))

    def searchControlsSetVisible(self, view):
        for w in [self.ui.searchInPage,
                  self.ui.searchCancel,
                  self.ui.searchButton,
                  self.ui.searchLabel,
                  self.ui.searchPrev,
                  self.ui.searchNext]:
            w.setVisible(view)

        self.ui.findToolButton.setChecked(view)

        if view is True:
            self.ui.searchInPage.setFocus(Qt.OtherFocusReason)
        else:
            self.webEngineView.setFocus(Qt.OtherFocusReason)

    def onToggleSearchControls(self):
        self.searchControlsSetVisible(not self.ui.searchInPage.isVisible())

    def onSearchInPageEdit(self, text):
        pass

    def onSearchInPage(self):
        self.searchInPage()

    def searchReset(self):
        self.ui.searchInPage.clear()
        self.searchInPage()

    def searchInPage(self, flags=0):
        text = self.ui.searchInPage.text()
        self.webEngineView.webPage.findText(
            text, QWebEnginePage.FindFlags(flags),
            self.searchCallback
        )

    def searchCallback(self, found):
        pass

    def onSearchInPageNext(self):
        self.searchInPage()

    def onSearchInPagePrev(self):
        self.searchInPage(QWebEnginePage.FindBackward)

    def onSearchCancel(self):
        self.searchReset()
        self.searchControlsSetVisible(False)

    def onJsConsoleToggle(self, checked):
        if not self.jsConsoleWidget.isVisible():
            self.jsConsoleWidget.show()

    async def onCreateMapping(self, *args):
        if not self.currentIpfsObject:
            return messageBox(iNotAnIpfsResource())

        await runDialogAsync(
            QSchemeCreateMappingDialog,
            self.currentIpfsObject,
            self.currentPageTitle
        )

    def onClipboardIpfs(self, pathObj):
        pass

    def onToggledPinAll(self, checked):
        pass

    def onFocusUrl(self):
        if self.webEngineView.pageLoading:
            # TODO: something nicer, or add another loadInterrupted var
            self.urlZone.loadInterruptedByEdit = True

        self.focusUrlZone(True, reason=Qt.ShortcutFocusReason)

    def focusUrlZone(self, select=False, reason=Qt.ActiveWindowFocusReason):
        self.urlZone.unobfuscate(selectUrl=select)
        self.urlZone.bar.setFocus(reason)

    def onReloadPage(self):
        self.reloadPage()

    def onReloadPageNoCache(self):
        self.reloadPage(bypassCache=True)

    def reloadPage(self, bypassCache=False):
        self.urlZone.unfocus()
        self.urlZone.resetState()
        self.webEngineView.triggerPageAction(
            QWebEnginePage.ReloadAndBypassCache if bypassCache is True else
            QWebEnginePage.Reload
        )

    def onSavePageToPdf(self):
        path = saveFileSelect(filter='(*.pdf)')
        if not path:
            return

        page = self.webView.page()

        try:
            page.printToPdf(path)
        except Exception:
            messageBox(iSaveWebPageToPdfFileError())
        else:
            messageBox(iSaveWebPageToPdfFileOk(path))

    def onSavePageContained(self):
        tmpd = self.app.tempDirCreate(self.app.tempDirWeb)
        if tmpd is None:
            return messageBox('Cannot create temporary directory')

        page = self.webView.page()

        url = page.url()
        filename = url.fileName()

        if not filename or cidValid(filename):
            filename = 'index.html'

        path = os.path.join(tmpd, filename)
        page.save(path, QWebEngineDownloadItem.CompleteHtmlSaveFormat)

    async def onHashmarkPage(self, *qta):
        try:
            langTag = await self.webEngineView.page().getPageLanguage()
        except Exception:
            pass

        if self.currentUrl and isUrlSupported(self.currentUrl):
            ensure(addHashmarkAsync(
                self.currentUrl.toString(),
                title=self.currentPageTitle,
                langTag=langTag
            ))
        elif self.currentIpfsObject and self.currentIpfsObject.valid:
            scheme = self.currentUrl.scheme()
            ensure(addHashmarkAsync(
                self.currentIpfsObject.fullPath,
                title=self.currentPageTitle,
                langTag=langTag,
                schemePreferred=scheme
            ))
        else:
            messageBox(iUnsupportedUrl())

    def onPinResult(self, f):
        try:
            path, code, msg = f.result()
        except:
            pass
        else:
            path = IPFSPath(path)
            if not path.valid:
                log.debug('Invalid path in pin result: {}'.format(str(path)))
                return

            if code == 0:
                self.app.systemTrayMessage('PIN', iPinSuccess(str(path)),
                                           timeout=2000)
            elif code == 1:
                self.app.systemTrayMessage('PIN', iPinError(str(path), msg),
                                           timeout=3000)
            elif code == 2:
                # Cancelled, no need to notify here
                pass
            else:
                log.debug('Unknown status code for pinning result')

    @ipfsOp
    async def pinQueuePath(self, ipfsop, path, recursive, notify):
        log.debug('Pinning object {0} (recursive: {1})'.format(path,
                                                               recursive))
        onSuccess = None
        if notify is True:
            onSuccess = self.onPinResult
        await ipfsop.ctx.pinner.queue(path, recursive, onSuccess,
                                      qname='browser')

    def pinPath(self, path, recursive=True, notify=True):
        if isinstance(path, str):
            ensure(self.pinQueuePath(path, recursive, notify))
        elif isinstance(path, IPFSPath):
            ensure(self.pinQueuePath(path.objPath, recursive, notify))

    def onPrintWebPage(self):
        printer = QPrinter(QPrinter.HighResolution)
        dialog = QPrintDialog(printer, self)

        def htmlRendered(htmlCode):
            if not printer.isValid():
                return messageBox('Invalid printer')

            edit = QTextEdit()
            edit.setHtml(htmlCode)
            edit.print_(printer)

        if dialog.exec_() == QDialog.Accepted:
            currentPage = self.webEngineView.page()
            currentPage.toHtml(htmlRendered)

    async def onPinPageLinks(self, ipfsPath: IPFSPath):
        def htmlReady(htmlCode):
            ensure(self.pinIpfsLinksInPage(htmlCode))

        self.webEngineView.webPage.toHtml(htmlReady)

    @ipfsOp
    async def pinIpfsLinksInPage(self, ipfsop, htmlCode):
        if not isinstance(htmlCode, str):
            return

        baseUrl = self.currentUrl.url(
            QUrl.RemoveFilename | QUrl.RemoveFragment | QUrl.RemoveQuery)
        basePath = IPFSPath(baseUrl)

        if not basePath.valid:
            return

        # Being a potentially CPU-intensive task for large documents, run
        # the HTML parser in the threadpool executor

        parser = IPFSLinksParser(basePath)
        logUser.info('Scanning links in object: {op}'.format(
            op=basePath))

        await self.app.loop.run_in_executor(self.app.executor,
                                            parser.feed, htmlCode)

        tab = PinBatchTab(self.app.mainWindow)
        bulkWidget = PinBatchWidget(basePath, parser.links, parent=tab)
        tab.addToLayout(bulkWidget)
        self.app.mainWindow.registerTab(tab, 'Pin batch', current=True,
                                        icon=getIcon('pin.png'))

    def onBrowseCurrentClipItem(self):
        current = self.app.clipTracker.getCurrent()
        if current:
            self.browseFsPath(IPFSPath(current.fullPath))
        else:
            messageBox(iClipboardEmpty())

    def onLoadIpfsCID(self):
        def onValidated(d):
            path = IPFSPath(d.getHash(), autoCidConv=True)
            if path.valid:
                self.browseFsPath(path)

        ensure(runDialogAsync(IPFSCIDInputDialog, title=iEnterIpfsCIDDialog(),
                              accepted=onValidated))

    def onLoadIpfsMultipleCID(self):
        def onValidated(dlg):
            # Open a tab for every CID
            cids = dlg.getCIDs()
            for cid in cids:
                path = IPFSPath(cid, autoCidConv=True)
                if not path.valid:
                    continue
                self.gWindow.addBrowserTab().browseFsPath(path)

        ensure(runDialogAsync(IPFSMultipleCIDInputDialog,
                              title=iEnterIpfsCIDDialog(),
                              accepted=onValidated))

    def onLoadIpns(self):
        text, ok = QInputDialog.getText(self,
                                        iEnterIpnsDialog(),
                                        iEnterIpns())
        if ok:
            self.browseIpnsKey(text)

    def onFollowIpns(self):
        if self.currentIpfsObject and self.currentIpfsObject.isIpns:
            root = self.currentIpfsObject.root().objPath
            ensure(runDialogAsync(AddFeedDialog, self.app.marksLocal,
                                  root,
                                  title=iFollowIpnsDialog()))

    def onLoadHome(self):
        self.loadHomePage()

    def loadHomePage(self):
        homeUrl = self.app.settingsMgr.getSetting(CFG_SECTION_BROWSER,
                                                  CFG_KEY_HOMEURL)
        self.enterUrl(QUrl(homeUrl))

    def refreshButtonClicked(self):
        self.webEngineView.reload()

    def stopButtonClicked(self):
        self.setLoadingStatus(False)
        self.urlZone.resetState()
        self.webEngineView.stop()
        self.ui.pBarBrowser.setValue(0)
        self.ui.stopButton.setEnabled(False)

    def backButtonClicked(self):
        self.urlZone.unfocus()
        currentPage = self.webEngineView.page()
        currentPage.history().back()

    def forwardButtonClicked(self):
        self.urlZone.unfocus()
        currentPage = self.webEngineView.page()
        currentPage.history().forward()

    def urlZoneInsert(self, url: QUrl):
        ensure(self.urlZone.setUrl(url))

    @asyncify
    async def onUrlChanged(self, url):
        if not url.isValid() or url.scheme() in ['data', SCHEME_Z]:
            return

        sHandler = self.webEngineView.webProfile.urlSchemeHandler(
            url.scheme().encode())

        urlAuthority = url.authority()

        self.hashmarkWAction.setEnabled(True)

        if url.scheme() in [SCHEME_IPFS, SCHEME_IPNS, SCHEME_DWEB]:
            self.urlZoneInsert(url)

            self._currentIpfsObject = IPFSPath(url.toString())
            self._currentUrl = url
            self.ipfsObjectVisited.emit(self.currentIpfsObject)

            self.pinToolButton.setEnabled(True)
            self.pinToolButton.changeObject(self.currentIpfsObject)

            self.followIpnsAction.setEnabled(
                self.currentIpfsObject.isIpns)
            self.curObjectCtrl.show()
        elif self.fromGateway(urlAuthority):
            # dweb:/ with IPFS gateway's authority
            # Content loaded from IPFS gateway, this is IPFS content

            self._currentIpfsObject = IPFSPath(
                url.toString(), autoCidConv=True)

            if self.currentIpfsObject.valid:
                log.debug('Current IPFS object: {0}'.format(
                    repr(self.currentIpfsObject)))

                nurl = QUrl(self.currentIpfsObject.dwebUrl)
                if url.hasFragment():
                    nurl.setFragment(url.fragment())
                if url.hasQuery():
                    nurl.setQuery(url.query())

                self.urlZoneInsert(nurl)

                self.pinToolButton.setEnabled(True)
                self.pinToolButton.changeObject(self.currentIpfsObject)

                self.ipfsObjectVisited.emit(self.currentIpfsObject)

                self._currentUrl = nurl

                # Activate the follow action if this is a root IPNS address
                self.followIpnsAction.setEnabled(
                    self.currentIpfsObject.isIpns)
                self.curObjectCtrl.show()
            else:
                log.debug(iInvalidUrl(url.toString()))
        else:
            if sHandler and issubclass(
                    sHandler.__class__, IPFSObjectProxyScheme):
                proxiedPath = await sHandler.urlProxiedPath(url)

                if proxiedPath and proxiedPath.valid:
                    self._currentIpfsObject = proxiedPath
                    self.ipfsObjectVisited.emit(self.currentIpfsObject)
                    # self.ui.hashmarkThisPage.setEnabled(True)
                    self.curObjectCtrl.show()
            else:
                # Non-IPFS browsing
                self._currentIpfsObject = None
                self.curObjectCtrl.hide()

            self.urlZoneInsert(url)
            self._currentUrl = url
            self.followIpnsAction.setEnabled(False)

        currentPage = self.webView.page()

        if currentPage:
            history = currentPage.history()

            self.ui.backButton.setEnabled(history.canGoBack())
            self.ui.forwardButton.setEnabled(history.canGoForward())

        self.webEngineView.setFocus(Qt.OtherFocusReason)

    def onTitleChanged(self, pageTitle):
        if pageTitle.startswith(self.gatewayAuthority):
            pageTitle = iNoTitle()

        self.currentPageTitle = pageTitle

        lenMax = 16
        if len(pageTitle) > lenMax:
            pageTitle = '{0} ...'.format(pageTitle[0:lenMax])

        if self.tabPageIdx >= 0:
            self.workspace.tabWidget.setTabText(self.tabPageIdx,
                                                pageTitle)
            self.workspace.tabWidget.setTabToolTip(self.tabPageIdx,
                                                   self.currentPageTitle)

    def currentUrlHistoryRecord(self):
        if not self.currentPageTitle:
            return

        if self.currentPageTitle == iNoTitle() or \
                self.currentPageTitle.startswith('about:'):
            return

        if self.currentUrl and self.currentUrl.isValid():
            self.history.record(self.currentUrl.toString(),
                                self.currentPageTitle)

    def onLoadFinished(self, ok):
        self.ui.stopButton.setEnabled(False)
        self.currentUrlHistoryRecord()

        self.urlZoneInsert(self.currentUrl)

        ensure(self.afterLoadScripts())

    @ipfsOp
    async def afterLoadScripts(self, ipfsop):
        """
        Run scripts that need to be executed after the page is loaded

        Password forms are handled here.
        """

        autoFillVars = ''
        profile = ipfsop.ctx.currentProfile
        ipid = await profile.userInfo.ipIdentifier()

        yurl = URL(
            self.currentUrl.toString()
        ).with_query('').with_fragment('')

        for cred in self.app.credsManager.forUrl(ipid.did,
                                                 yurl):
            ufield = cred.get('username_field')
            pwfield = cred.get('password_field')
            username = cred.get('username')
            password = cred.get('password')

            autoFillVars += f"autoFillVals['{ufield}'] = '{username}';\n"
            autoFillVars += f"autoFillVals['{pwfield}'] = '{password}';\n"

        if autoFillVars:
            script = scriptFromQFile(
                'autofill-password-forms',
                ':/share/js/autofill/AutoFillPasswordForms.js'
            )

            await self.webView.page().runJs(
                script.sourceCode() % autoFillVars
            )

    async def onIconChanged(self, icon):
        self.workspace.tabWidget.setTabIcon(self.tabPageIdx, icon)

    def setLoadingStatus(self, loading: bool):
        self.webEngineView.pageLoading = loading

    def onLoadStarted(self):
        self.setLoadingStatus(True)

        if not self.currentUrl:
            self.stackShowLoading()

    def applyStyleSheet(self, styleName: str):
        # Apply stylesheets
        webProfile = self.webEngineView.webProfile

        styleScripts = webProfile.webStyles.get(styleName)

        if styleScripts:
            for script in styleScripts:
                self.webEngineView.page().runJavaScript(
                    script.sourceCode(),
                    QWebEngineScript.ApplicationWorld
                )

    def onLoadProgress(self, progress):
        self.ui.pBarBrowser.setValue(progress)
        self.ui.stopButton.setEnabled(progress >= 0 and progress < 100)

        if progress == 100:
            self.setLoadingStatus(False)
            self.loop.call_later(
                1,
                self.ui.pBarBrowser.setStyleSheet,
                '''QProgressBar::chunk#pBarBrowser {
                    background-color: transparent;
                }''')
            self.ui.stopButton.hide()
            self.ui.reloadPageButton.show()

            self.webLoadingWidget.hide()
            self.webEngineView.noGraphicsEffect()

            # Show the webengine and remove any graphics effect
            self.stackShowWebEngine()
        else:
            self.setLoadingStatus(True)

            if progress in range(0, 60):
                self.webLoadingWidget.loading(progress)
                self.webEngineView.blur()
            elif progress in range(60, 99):
                self.webLoadingWidget.hide()
                self.webEngineView.noGraphicsEffect()
                self.stackShowWebEngine()

            self.ui.pBarBrowser.setStyleSheet(
                '''QProgressBar::chunk#pBarBrowser {
                    background-color: #4b9fa2;
                }''')
            self.ui.reloadPageButton.hide()
            self.ui.stopButton.show()

    def browseFsPath(self, path, schemePreferred='ipfs'):
        def _handle(iPath):
            if iPath.valid and not schemePreferred or \
                    schemePreferred in [SCHEME_IPFS, SCHEME_IPNS]:
                self.enterUrl(QUrl(iPath.ipfsUrl))
            elif iPath.valid and schemePreferred == 'dweb':
                self.enterUrl(QUrl(iPath.dwebUrl))
            else:
                messageBox(iInvalidObjectPath(iPath.fullPath))

        if isinstance(path, str):
            ipfsPath = IPFSPath(path, autoCidConv=True)
            return _handle(ipfsPath)
        elif isinstance(path, IPFSPath):
            return _handle(path)

    def browseIpfsHash(self, ipfsHash):
        if not cidhelpers.cidValid(ipfsHash):
            return messageBox(iInvalidCID(ipfsHash))

        self.browseFsPath(IPFSPath(joinIpfs(ipfsHash), autoCidConv=True))

    def browseIpnsKey(self, ipnsHash):
        self.browseFsPath(IPFSPath(joinIpns(ipnsHash)))

    def enterUrl(self, url):
        self.urlZone.hideMatches()
        self.urlZone.cancelTimer()

        if not url.isValid() or url.scheme() in ['data', SCHEME_Z]:
            messageBox('Invalid URL: {0}'.format(url.toString()))
            return

        self.urlZone.urlEditing = False
        self.urlZone.clearFocus()

        log.debug('Entering URL {}'.format(url.toString()))

        handler = self.webEngineView.webProfile.urlSchemeHandler(
            url.scheme().encode())

        def onEnsTimeout():
            pass

        if url.scheme() == SCHEME_DWEB:
            yUrl = URL(url.toString())
            if len(yUrl.parts) == 3:
                url.setPath(url.path() + '/')

        if not url.path():
            url.setPath('/')

        if url.scheme() == SCHEME_ENS:
            self.resolveTimer.timeout.connect(onEnsTimeout)
            self.resolveTimer.start(self.resolveTimerEnsMs)

        if handler:
            if hasattr(handler, 'webProfileNeeded'):
                wpName = handler.webProfileNeeded
                if self.webEngineView.webProfile.profileName != wpName and \
                        wpName in self.app.webProfiles:
                    self.changeWebProfileByName(wpName)

        self.urlZoneInsert(url)

        self.webEngineView.load(url)
        self.webEngineView.setFocus(Qt.OtherFocusReason)

        ensure(self.installGreaseMonkeyScripts(handler, url))

        self.jsConsole.log(f'URL changed: <b>{url.toString()}</b>')

    async def runIpfsSearch(self, queryStr):
        page = await self.webEngineView.setSearchPage()
        page.handler.cancelSearchTasks()
        page.handler.formReset()
        page.handler.search(queryStr, 'all')

    async def handleEditedUrl(self, inputStr):
        self.urlZone.cancelTimer()
        self.urlZone.hideMatches()
        self.urlZone.unfocus()

        engineMatch = re.search(r'^\s*(d|s|sx|c|i|ip)\s(.*)$', inputStr)
        if engineMatch:
            sUrl = None
            engine = engineMatch.group(1)
            search = engineMatch.group(2)

            if engine == 'd':
                sUrl = QUrl('https://duckduckgo.com')
                uq = QUrlQuery()
                uq.addQueryItem('q', quote(search))
                sUrl.setQuery(uq)

            elif engine in ['s', 'sx']:
                sUrl = QUrl('https://searx.org/search')
                uq = QUrlQuery()
                uq.addQueryItem('q', quote(search))
                sUrl.setQuery(uq)

            if engine in ['i', 'ip']:
                return await self.runIpfsSearch(search)

            if sUrl:
                log.debug(f'Searching with {sUrl.toString()}')
                return self.enterUrl(sUrl)

        #
        # Handle seamless upgrade of CIDv0, suggested by @lidel
        #
        # If the user uses the native scheme (ipfs://) but passes
        # a base58-encoded CID as host (whatever the version),
        # convert it to base32 with cidhelpers.cidConvertBase32()
        # and replace the old CID in the URL
        #
        # https://github.com/pinnaculum/galacteek/issues/5
        #

        if inputStr.startswith('ipfs://'):
            # Home run
            match = cidhelpers.ipfsDedSearchPath58(inputStr)
            if match:
                rootcid = match.group('rootcid')
                if rootcid and re.search('[A-Z]', rootcid):
                    # Has uppercase characters .. Either CIDv0
                    # or base58-encoded CIDv1
                    # If the conversion to base32 is successfull,
                    # replace the base58-encoded CID in the URL with
                    # the base32-encoded CIDv1

                    cid = cidhelpers.cidConvertBase32(rootcid)
                    if cid:
                        inputStr = re.sub(rootcid, cid, inputStr,
                                          count=1)
                    else:
                        return messageBox(iInvalidCID(rootcid))

        # ipfs+http CIDv0 => CIDv1 upgrade if necessary
        if inputStr.startswith('ipfs+http://'):
            match = cidhelpers.ipfsHttpSearch(inputStr)
            if match:
                peerId = match.group('peerid')
                peerIdV1 = cidhelpers.peerIdBase36(peerId)

                if peerId and re.search('[A-Z]', peerId) and peerIdV1:
                    inputStr = re.sub(peerId,
                                      peerIdV1,
                                      inputStr,
                                      count=1)

        url = QUrl(inputStr)
        # if not url.isValid() or not url.scheme():
        if not url.isValid() and 0:
            # Invalid URL or no scheme given
            # If the address bar contains a valid CID or IPFS path, load it
            iPath = IPFSPath(inputStr, autoCidConv=True)

            if iPath.valid:
                return self.browseFsPath(iPath)
            else:
                return messageBox(iInvalidUrl(inputStr))

        scheme = url.scheme()

        # Decide if we're using any web3 channel for this scheme
        if schemeSectionMatch(scheme, 'dapps'):
            # dapp

            channel = self.app.browserRuntime.web3Channel(scheme)

            if channel:
                log.debug(f'Using web3 channel for {scheme}: {channel}')
                self.webEngineView.web3ChangeChannel(channel)
                channel.webChannelDebug()
            else:
                log.debug(f'No web3 channel for {scheme}')
        else:
            self.webEngineView.webPage.changeWebChannel(None)

            log.debug(f'No using any web3 channel for {scheme}')

        self.webEngineView.setBrowserPage()

        if isSchemeRegistered(scheme):
            self.enterUrl(url)
        elif scheme in [SCHEME_HTTP, SCHEME_HTTPS, SCHEME_FTP]:
            # Browse http urls if allowed
            self.enterUrl(url)
        else:
            iPath = IPFSPath(inputStr, autoCidConv=True)

            if iPath.valid:
                return self.browseFsPath(iPath)

            if not validators.domain(inputStr) and 0:
                # Search
                await self.runIpfsSearch(inputStr)
                return

            tld = '.'.join(inputStr.split('.')[-1:])

            if tld == 'eth':
                self.enterUrl(QUrl(f'{SCHEME_ENS}://{inputStr}'))
            elif len(tld) in range(2, 4):
                self.enterUrl(QUrl(f'{SCHEME_HTTPS}://{inputStr}'))

    def onEnsResolved(self, domain, path):
        logUser.info('ENS: {0} maps to {1}'.format(domain, path))

    def setZoom(self, factor):
        self.webView.setZoomFactor(factor)

    def setZoomPercentage(self, pct: int):
        self.webView.setZoomFactor(self.zoomPercentToFactor(pct))

    def currentZoom(self):
        return self.webView.zoomFactor()

    def zoomPercentToFactor(self, pct: int):
        if pct in range(0, 300):
            return float(pct / 100)

        return 1.0

    def onZoomIn(self):
        cFactor = self.webView.zoomFactor()
        self.setZoom(cFactor + 0.25)

    def onZoomOut(self):
        cFactor = self.webView.zoomFactor()
        self.setZoom(cFactor - 0.25)

    def onViewProntoGraph(self, action: QAction):
        graphUri = str(action.data())

        if graphUri:
            self.enterUrl(QUrl(f'{SCHEME_PRONTO_GRAPHS}:/{graphUri}'))

    def configure(self):
        pass
