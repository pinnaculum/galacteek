import functools

from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QStackedWidget
from PyQt5.QtQuickWidgets import QQuickWidget

from PyQt5.QtPrintSupport import *

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
from galacteek import database

from galacteek.browser.schemes import SCHEME_FTP
from galacteek.browser.schemes import SCHEME_HTTP

from galacteek.ld.rdf.hashmarks import searchLdHashmarks

from galacteek.qml import quickWidgetFromLibrary

from galacteek.ipfs.wrappers import *

from ..helpers import *
from ..i18n import *
from ..widgets import *

from galacteek.appsettings import *
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

    def __init__(self, history, historyView, browserTab, parent=None):
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

        self.stack.addWidget(self.urlBar)
        self.stack.addWidget(self.obs)
        self.stack.setCurrentIndex(0)

        self.history = history
        self.historyMatches = historyView
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
        self.historyMatches.historyItemSelected.connect(
            self.onHistoryItemSelected)
        self.historyMatches.collapsed.connect(
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
    def matchesVisible(self):
        return self.historyMatches.isVisible()

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

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Up:
            self.historyMatches.activateWindow()
            self.historyMatches.setFocus(Qt.OtherFocusReason)
        elif ev.key() == Qt.Key_Down:
            self.historyMatches.activateWindow()
            self.historyMatches.setFocus(Qt.OtherFocusReason)
        elif ev.key() == Qt.Key_Escape:
            self.hideMatches()
        else:
            super().keyPressEvent(ev)

    def unfocus(self):
        self.urlEditing = False
        self.bar.clearFocus()

    def cancelTimer(self):
        self.editTimer.stop()

    def hideMatches(self):
        self.historyMatches.hide()

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
        self.setFocus(Qt.PopupFocusReason)
        self.bar.deselect()

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
        ensure(self.historyLookup())

    def historyMatchesPopup(self):
        lEditPos = self.mapToGlobal(QPoint(0, 0))
        lEditPos.setY(lEditPos.y() + self.height())
        self.historyMatches.move(lEditPos)
        self.historyMatches.resize(QSize(
            self.app.desktopGeometry.width() - self.pos().x() - 64,
            self.height() * 8
        ))
        self.historyMatches.show()
        # Refocus
        # self.setFocus(Qt.PopupFocusReason)

    async def historyLookupStraight(self):
        if self.urlInput:
            await self.historyMatches.lookup(self.urlInput)
            self.historyMatchesPopup()

    async def historyLookup(self):
        if self.urlInput:
            markMatches = []

            markMatches = await database.hashmarksSearch(
                query=self.urlInput
            )

            ldMarkMatches = await searchLdHashmarks(
                title=self.urlInput
            )

            hMatches = await self.history.match(self.urlInput)

            if len(markMatches) > 0 or len(hMatches) > 0 or ldMarkMatches:
                await self.historyMatches.showMatches(markMatches, hMatches,
                                                      ldMarkMatches)

                self.historyMatchesPopup()
            else:
                self.hideMatches()

            self.editTimer.stop()
        else:
            self.hideMatches()

    def onHistoryItemSelected(self, urlStr):
        self.historyMatches.hide()
        self.urlEditing = False

        url = QUrl(urlStr)

        if url.isValid():
            self.browserTab.enterUrl(url)
