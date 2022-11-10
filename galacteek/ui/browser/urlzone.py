import functools

from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QStackedWidget
from PyQt5.QtQuickWidgets import QQuickWidget

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QEvent
from PyQt5.QtCore import QUrl
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import QPoint
from PyQt5.QtCore import QSize

from PyQt5.QtGui import QPalette
from PyQt5.QtGui import QColor

from galacteek import ensure
from galacteek import partialEnsure

from galacteek.browser.schemes import SCHEME_FTP
from galacteek.browser.schemes import SCHEME_HTTP

from galacteek.qml import quickWidgetFromLibrary

from .graphsearch import ContentSearchResultsTree

from ..notify import uiNotify
from ..helpers import *
from ..widgets import *

from galacteek.ui.urls import urlColor


class URLBeclouderWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.app = QCoreApplication.instance()
        self.hLayout = QHBoxLayout()
        self.setLayout(self.hLayout)

        self.cloud = quickWidgetFromLibrary(
            'DWebViewURLCloud.qml',
            parent=self
        )

        self.cloud.setAttribute(Qt.WA_AlwaysStackOnTop)
        self.cloud.setAttribute(Qt.WA_TranslucentBackground)
        self.cloud.setClearColor(Qt.transparent)
        self.cloud.setResizeMode(QQuickWidget.SizeRootObjectToView)

        self.hLayout.addWidget(self.cloud)
        self.setMouseTracking(True)

    @property
    def rootObject(self):
        return self.cloud.rootObject()

    def onUrlChanged(self, url: QUrl):
        pass

    def onUrlHovered(self, url: QUrl):
        self.rootObject.urlHoveredAnimate(url, True)

    def setAnimationStatus(self, active: bool):
        # Show or interrupt the URL particles animation
        self.rootObject.urlAnimate(active)

    async def beCloud(self, url: QUrl):
        self.setToolTip(url.toString())

        color = await urlColor(url)

        if color:
            self.rootObject.changeUrl(url, color)
            self.rootObject.update()


class URLInputWidget(QWidget):
    maxHeight = 128
    urlChanged = pyqtSignal(QUrl)

    pageUrlHovered = pyqtSignal(QUrl)

    def __init__(self, history,
                 contentSearch: ContentSearchResultsTree,
                 browserTab,
                 parent=None):
        super(URLInputWidget, self).__init__(parent=parent)

        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setMouseTracking(True)

        self.app = QCoreApplication.instance()
        self.hLayout = QHBoxLayout()
        self.setLayout(self.hLayout)
        self.stack = QStackedWidget(parent=self)
        self.stack.setObjectName('urlZoneStack')

        self.hLayout.addWidget(self.stack)

        self.urlBar = QLineEdit(parent=self.stack)
        self.urlBar.setClearButtonEnabled(True)

        self.obs = URLBeclouderWidget(parent=self.stack)
        self.obs.rootObject.cloudClicked.connect(self.handleMouseClick)

        self.urlChanged.connect(self.obs.onUrlChanged)
        self.pageUrlHovered.connect(self.obs.onUrlHovered)

        self.stack.addWidget(self.urlBar)
        self.stack.addWidget(self.obs)
        self.stack.setCurrentIndex(0)

        self.history = history
        self.contentSearch = contentSearch
        self.browserTab = browserTab

        self.setObjectName('urlZone')
        self.urlBar.setObjectName('urlBar')

        self.urlBar.setDragEnabled(True)
        self.urlBar.setMaxLength(1024)

        self.urlEditing = False
        self.urlInput = None
        self.loadInterruptedByEdit = False

        self.editTimer = QTimer(self)
        self.editTimer.timeout.connect(self.onTimeoutUrlEdit)
        self.editTimer.setSingleShot(True)

        self.urlBar.returnPressed.connect(partialEnsure(self.onReturnPressed))
        self.contentSearch.historyItemSelected.connect(
            self.onHistoryItemSelected)
        self.contentSearch.collapsed.connect(
            self.onHistoryCollapse)
        self.urlBar.textEdited.connect(self.onUrlUserEdit)

        self.destroyed.connect(functools.partial(self.onDestroyed))

    @property
    def editTimeoutMs(self):
        return 400

    @property
    def bar(self):
        return self.urlBar

    @property
    def currentUrl(self):
        return QUrl(self.bar.text())

    @property
    def matchesVisible(self):
        return self.contentSearch.isVisible()

    def onDestroyed(self):
        self.obs.deleteLater()

    def selectUrl(self):
        self.bar.setSelection(0, len(self.bar.text()))

    def handleMouseClick(self):
        if self.stack.currentWidget() is self.obs:
            if self.browserTab.webEngineView.pageLoading:
                # edit while loading
                self.loadInterruptedByEdit = True

            self.unobfuscate()

    def mousePressEvent(self, ev):
        self.handleMouseClick()

        super().mousePressEvent(ev)

    def clear(self):
        # Clear URL bar
        self.urlBar.clear()

    def resetState(self):
        self.loadInterruptedByEdit = False

    def unobfuscate(self, selectUrl: bool = True):
        self.startStopUrlAnimation(False)
        self.stack.setCurrentIndex(0)

        if selectUrl:
            self.selectUrl()

    async def obfuscate(self, url: QUrl):
        if self.loadInterruptedByEdit:
            return

        self.urlEditing = False
        self.hideMatches()
        self.stack.setCurrentIndex(1)

        await self.obs.beCloud(url)

        self.startStopUrlAnimation(True)

    async def setUrl(self, url: QUrl):
        if not isinstance(url, QUrl) or not url.isValid():
            return

        urls = url.toString()

        if urls != self.urlBar.text():
            self.clear()

            self.urlBar.insert(urls)
            self.urlBar.setCursorPosition(0)
            self.urlChanged.emit(url)

        nonObfuscatedSchemes = [
            SCHEME_FTP,  # cry, then
            SCHEME_HTTP  # be ashamed
        ]

        if url.scheme() not in nonObfuscatedSchemes:
            """
            Obfuscate the URL bar input for this scheme
            """

            await self.obfuscate(url)

    def setupPalette(self):
        palette = self.palette()
        palette.setColor(QPalette.HighlightedText, ipfsColor1)
        palette.setColor(QPalette.Highlight, QColor('transparent'))
        self.setPalette(palette)

    def enterContentSearch(self):
        self.contentSearch.selectFirstItem()
        self.contentSearch.activateWindow()
        self.contentSearch.setFocus(Qt.OtherFocusReason)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Up:
            self.contentSearch.activateWindow()
            self.contentSearch.setFocus(Qt.OtherFocusReason)
        elif ev.key() == Qt.Key_Down:
            if not self.contentSearch.hasFocus():
                self.enterContentSearch()
        elif ev.key() == Qt.Key_Escape:
            self.hideMatches()

            if self.currentUrl.isValid() and self.currentUrl.scheme():
                ensure(self.obfuscate(self.currentUrl))

        super().keyPressEvent(ev)

    def unfocus(self):
        self.urlEditing = False
        self.bar.clearFocus()

    def cancelTimer(self):
        self.editTimer.stop()

    def hideMatches(self):
        try:
            self.contentSearch.hide()
        except Exception:
            pass

    def startStopUrlAnimation(self, active: bool):
        self.obs.setAnimationStatus(
            self.stack.currentWidget() is self.obs and active
        )

    async def onReturnPressed(self):
        self.resetState()
        self.urlEditing = False

        self.unfocus()

        await self.browserTab.handleEditedUrl(self.bar.text())

    def onHistoryCollapse(self):
        self.bar.setFocus(Qt.PopupFocusReason)

    def changeEvent(self, event: QEvent):
        super().changeEvent(event)

    def showEvent(self, ev):
        super().showEvent(ev)

    def hideEvent(self, event):
        self.hideMatches()

        super().hideEvent(event)

    def focusInEvent(self, event):
        if event.reason() in [Qt.ShortcutFocusReason, Qt.MouseFocusReason,
                              Qt.PopupFocusReason, Qt.ActiveWindowFocusReason,
                              Qt.TabFocusReason]:
            self.urlEditing = True

        super(URLInputWidget, self).focusInEvent(event)

    def focusOutEvent(self, event):
        if event.reason() not in [
                Qt.ActiveWindowFocusReason,
                Qt.PopupFocusReason,
                Qt.TabFocusReason,
                Qt.OtherFocusReason]:
            self.urlEditing = False
            self.editTimer.stop()

        super(URLInputWidget, self).focusOutEvent(event)

    def onUrlTextChanged(self, text):
        pass

    def onUrlUserEdit(self, text):
        self.urlInput = text

        if not self.bar.hasFocus():
            return

        self.startEditTimer()

    def startEditTimer(self):
        if not self.editTimer.isActive():
            self.editTimer.start(self.editTimeoutMs)
        else:
            self.editTimer.stop()
            self.editTimer.start(self.editTimeoutMs)

    def onTimeoutUrlEdit(self):
        ensure(self.graphSearchForContent())

    def resizeEvent(self, event):
        self.setBoundaries()

    def setBoundaries(self):
        self.contentSearch.setMinimumSize(
            self.width(),
            0.3 * self.app.desktopGeometry.height()
        )

        self.contentSearch.setMaximumSize(
            self.width(),
            max(
                max(self.contentSearch.resultsCount, 12) * 32,
                self.height() * 0.8
            )
        )

    def contentSearchPopup(self):
        lEditPos = self.mapToGlobal(QPoint(0, 0))
        lEditPos.setY(lEditPos.y() + self.height())

        self.contentSearch.resize(QSize(
            self.bar.width(),
            self.contentSearch.resultsCount * 16
        ))

        self.contentSearch.move(lEditPos)
        self.contentSearch.show()

    async def graphSearchForContent(self):
        if self.urlInput:
            self.editTimer.stop()

            self.contentSearch.lookup(self.urlInput)

            if self.contentSearch.resultsCount > 0:
                self.contentSearchPopup()

                if self.contentSearch.resultsCount == 1:
                    # Lucky day

                    self.enterContentSearch()

                    uiNotify('luckySearch')
            else:
                self.hideMatches()
        else:
            self.hideMatches()

    def onHistoryItemSelected(self, urlStr):
        self.contentSearch.hide()
        self.urlEditing = False

        url = QUrl(urlStr)

        if url.isValid():
            self.browserTab.enterUrl(url)
