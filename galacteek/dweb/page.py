from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebEngineWidgets import QWebEnginePage
from PyQt5.QtWebEngineWidgets import QWebEngineSettings
from PyQt5.QtWebChannel import QWebChannel

from PyQt5.QtCore import QObject, pyqtSlot, pyqtSignal
from PyQt5.QtCore import QJsonValue, QVariant, QUrl

from PyQt5.QtWidgets import QApplication, QSizePolicy

from galacteek.ui.widgets import GalacteekTab
from galacteek import ensure
from galacteek import log
from galacteek.dweb.render import renderTemplate
from galacteek.dweb.webscripts import ipfsClientScripts, orbitScripts

import asyncio
import functools


class BaseHandler(QObject):
    def __init__(self, parent):
        super().__init__(parent)

    @pyqtSlot()
    def test(self):
        pass

    def awrap(self, fn, *args, **kw):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(functools.partial(fn, *args, **kw))


class GalacteekHandler(QObject):
    def __init__(self, parent):
        super().__init__(parent)
        self.app = QApplication.instance()

    @pyqtSlot(str)
    def openIpfsLink(self, path):
        tab = self.app.mainWindow.addBrowserTab()
        tab.browseFsPath(path)


class BasePage(QWebEnginePage):
    def __init__(self, template, url=None, parent=None):
        super(BasePage, self).__init__(parent)
        self.app = QApplication.instance()
        self.template = template
        self._handlers = {}
        self.channel = QWebChannel()
        self.url = url if url else QUrl('qrc:/')
        self.setWebChannel(self.channel)
        self.webScripts = self.profile().scripts()

        self.settings().setAttribute(QWebEngineSettings.LocalStorageEnabled,
                                     True)
        self.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls,
                                     True)
        self.installScripts()
        ensure(self.render())

    def installScripts(self):
        pass

    def register(self, name, obj):
        self.channel.registerObject(name, obj)
        self._handlers[name] = obj

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceId):
        log.debug(
            'JS: level: {0}, source: {1}, line: {2}, message: {3}'.format(
                level,
                sourceId,
                lineNumber,
                message))

    async def render(self):
        self.setHtml(await renderTemplate(self.template,
                                          baseUrl=self.url))


class OrbitPage(BasePage):
    def installScripts(self):
        exSc = self.webScripts.findScript('ipfs-http-client')
        if exSc.isNull():
            log.debug('Adding ipfs-http-client scripts')

            scripts = ipfsClientScripts(self.app.getIpfsConnectionParams())
            for script in scripts:
                self.webScripts.insert(script)

        exSc = self.webScripts.findScript('orbit-db')
        if exSc.isNull():
            log.debug('Adding orbit-db scripts')
            scripts = orbitScripts(self.app.getIpfsConnectionParams())
            for script in scripts:
                self.webScripts.insert(script)


class HashmarksHandler(BaseHandler):
    marksListed = pyqtSignal(str, QJsonValue)

    def __init__(self, marksLocal, parent=None):
        super(HashmarksHandler, self).__init__(parent)
        self.marksLocal = marksLocal

    @pyqtSlot(result=list)
    def categories(self):
        cats = self.marksLocal.getCategories()
        return cats

    @pyqtSlot(str, result=QJsonValue)
    def marks(self, cat):
        marks = self.marksLocal.getCategoryMarks(cat)
        return QJsonValue.fromVariant(QVariant(marks))


class HashmarksPage(BasePage):
    def __init__(self, marksLocal, parent=None):
        super(HashmarksPage, self).__init__('hashmarks.html', parent=parent)

        self.marksLocal = marksLocal
        self.marksLocal.changed.connect(self.onMarksChanged)
        self.hashmarks = HashmarksHandler(self.marksLocal, self)
        self.register('hashmarks', self.hashmarks)
        self.register('galacteek', GalacteekHandler(None))

    def onMarksChanged(self):
        ensure(self.render())

    async def render(self):
        self.setHtml(await renderTemplate(
            self.template,
            marks=self.marksLocal),
            baseUrl=QUrl('qrc:/'))


class DWebView(QWebEngineView):
    def __init__(self, page=None, parent=None):
        super(DWebView, self).__init__(parent)
        self.channel = QWebChannel()
        self.p = page
        self.show()

    @property
    def p(self):
        return self._currentPage

    @p.setter
    def p(self, page):
        if page:
            self._currentPage = page
            self.setPage(page)


class WebTab(GalacteekTab):
    def __init__(self, mainW):
        super(WebTab, self).__init__(mainW)

    def attach(self, view):
        self.vLayout.addWidget(view)
