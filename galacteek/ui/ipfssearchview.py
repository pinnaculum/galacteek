import asyncio
import time

from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtWebEngineWidgets import QWebEngineScript
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtCore import QObject, pyqtSlot, pyqtSignal
from PyQt5.QtCore import QJsonValue, QUrl, QFile

from PyQt5.QtWidgets import QWidget, QStackedWidget, QStyle, QApplication
from PyQt5.QtCore import (Qt, pyqtSignal, QRegularExpression)
from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QFont
from PyQt5.Qt import QByteArray

from galacteek.ipfs.cidhelpers import cidValid
from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.wrappers import ipfsOp
from galacteek.ipfs import ipfssearch
from galacteek.dweb.render import renderTemplate, defaultJinjaEnv
from galacteek.dweb.webscripts import ipfsClientScripts, orbitScripts
from galacteek import ensure

from . import ui_ipfssearchw, ui_ipfssearchwresults, ui_ipfssearchbrowser
from .helpers import *
from .hashmarks import *
from .widgets import *
from .i18n import *


def iResultsInfo(count, maxScore):
    return QCoreApplication.translate(
        'IPFSSearchResults',
        'Results count: <b>{0}</b> (max score: <b>{1}</b>)').format(
        count,
        maxScore)


def iNoResults():
    return QCoreApplication.translate('IPFSSearchResults',
                                      '<b>No results found</b>')


def iErrFetching():
    return QCoreApplication.translate('IPFSSearchResults',
                                      '<b>Error while fetching results</b>')


def iSearching():
    return QCoreApplication.translate('IPFSSearchResults',
                                      '<b>Searching ...</b>')


class Highlighter(QSyntaxHighlighter):
    """
    Highlights the search query string in the results
    """

    def __init__(self, highStr, doc):
        super().__init__(doc)

        self.highStr = highStr
        self.fmt = QTextCharFormat()
        self.fmt.setFontWeight(QFont.Bold)
        self.fmt.setForeground(Qt.red)

    def highlightBlock(self, text):
        rExpr = QRegularExpression(self.highStr)
        matches = rExpr.globalMatch(text)

        if not matches.isValid():
            return

        while matches.hasNext():
            match = matches.next()
            if not match.isValid():
                break
            self.setFormat(match.capturedStart(), match.capturedLength(),
                           self.fmt)


class NoResultsPage(QWebEnginePage):
    def __init__(self, tmpl, parent=None):
        super(NoResultsPage, self).__init__(parent)
        self.setHtml('<html><body><p>NO RESULTS</p></body></html>')


class SearchInProgressPage(QWebEnginePage):
    def __init__(self, tmpl, parent=None):
        super(SearchInProgressPage, self).__init__(parent)
        self.template = tmpl
        ensure(self.render())

    async def render(self):
        self.setHtml(await renderTemplate(self.template))


class SearchResultsPage(QWebEnginePage):
    def __init__(
            self,
            handler,
            tmplMain,
            tmplHits,
            ipfsConnParams,
            parent=None):
        super(SearchResultsPage, self).__init__(parent)
        self.app = QApplication.instance()
        self.handler = handler
        self.template = tmplMain
        self.templateHits = tmplHits
        self.ipfsConnParams = ipfsConnParams
        self.noStatTimeout = 12
        self.installScripts()
        ensure(self.render())

    def installScripts(self):
        self.webScripts = self.profile().scripts()

        exSc = self.webScripts.findScript('ipfs-http-client')
        if self.app.settingsMgr.jsIpfsApi is True and exSc.isNull():
            log.debug('Adding ipfs-http-client scripts')

            scripts = ipfsClientScripts(self.app.getIpfsConnectionParams())
            for script in scripts:
                self.webScripts.insert(script)
            scripts = orbitScripts(self.app.getIpfsConnectionParams())
            for script in scripts:
                self.webScripts.insert(script)

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceId):
        log.info(
            'JS: level: {0}, source: {1}, line: {2}, message: {3}'.format(
                level,
                sourceId,
                lineNumber,
                message))

    async def render(self):
        self.setHtml(await renderTemplate(self.template),
                     baseUrl=QUrl('qrc:/'))

    def renderHits(self, results):
        ctxHits = []

        for hit in results.hits:
            hitHash = hit.get('hash', None)
            mimeType = hit.get('mimetype', None)

            if hitHash is None or not cidValid(hitHash):
                continue

            path = joinIpfs(hitHash)
            sizeFormatted = sizeFormat(hit.get('size', 0))

            ctxHits.append({
                'hash': hitHash,
                'path': path,
                'mimetype': mimeType if mimeType else '',
                'title': hit.get('title', iUnknown()),
                'size': hit.get('size', iUnknown()),
                'sizeformatted': sizeFormatted,
                'description': hit.get('description', None),
                'type': hit.get('type', iUnknown()),
                'first-seen': hit.get('first-seen', iUnknown())
            })

            ensure(self.fetchObjectStat(hitHash, path))

        r = self.templateHits.render(hits=ctxHits,
                                     resultsCount=results.resultsCount,
                                     pageCount=results.pageCount,
                                     ipfsConnParams=self.ipfsConnParams)
        return r

    @ipfsOp
    async def fetchObjectStat(self, op, cid, path):
        def statCallback(f):
            try:
                result = f.result()
            except BaseException as err:
                log.debug('Exception on stat', exc_info=err)
                return
            if isinstance(result, dict):
                self.handler.objectStatAvailable.emit(cid, result)
            else:
                self.handler.objectStatUnavailable.emit(cid)

        if path not in op.ctx.objectStats:
            f = ensure(op.objStatCtxUpdate(path, timeout=self.noStatTimeout))
            f.add_done_callback(statCallback)
        else:
            stat = op.ctx.objectStats.get(path)
            if stat is None:
                self.handler.objectStatUnavailable.emit(cid)


class Handler(QObject):
    ready = pyqtSignal()
    resultsReady = pyqtSignal(list)
    resultsReadyDom = pyqtSignal(str)
    objectReady = pyqtSignal(str)
    objectStatAvailable = pyqtSignal(str, dict)
    objectStatUnavailable = pyqtSignal(str)

    def __init__(self, parent):
        super().__init__(parent)
        self.searchW = parent
        self.results = None

    @pyqtSlot()
    def mimeText(self):
        pass

    @pyqtSlot(str)
    def fetchObject(self, path):
        ensure(self.fetch(path))

    @pyqtSlot(str)
    def pinObject(self, path):
        ensure(self.pin(path))

    @ipfsOp
    async def pin(self, op, path):
        pinner = op.ctx.pinner
        await pinner.queue(path, False, None)

    @ipfsOp
    async def fetch(self, op, path):
        import tempfile
        try:
            data = await asyncio.wait_for(
                op.client.cat(path), 5)
        except BaseException:
            pass
        else:
            file = tempfile.NamedTemporaryFile(delete=False)
            file.write(data)
            self.objectReady.emit(file.name)

    @pyqtSlot(str)
    def openLink(self, path):
        tab = self.searchW.gWindow.addBrowserTab()
        tab.browseFsPath(path)

    @pyqtSlot(str)
    def hashmark(self, path):
        hashV = stripIpfs(path)

        if not self.results:
            return

        hit = self.results.findByHash(hashV)
        title = hit.get('title', iUnknown()) if hit else ''
        descr = hit.get('description', iUnknown()) if hit else ''

        addHashmark(self.searchW.app.marksLocal,
                    path, title, description=descr)

    @pyqtSlot(str)
    def explore(self, path):
        hashV = stripIpfs(path)
        if hashV:
            mainW = self.searchW.app.mainWindow
            mainW.exploreHash(hashV)


class IPFSSearchView(GalacteekTab):
    resultsReceived = pyqtSignal(ipfssearch.IPFSSearchResults, bool)

    def __init__(self, searchQuery, *args, **kw):
        super(IPFSSearchView, self).__init__(*args, **kw)

        self.setAttribute(Qt.WA_DeleteOnClose)

        # Templates
        self.resultsTemplate = self.app.getJinjaTemplate('ipfssearch.html')
        self.hitsTemplate = self.app.getJinjaTemplate('ipfssearch-hits.html')
        self.loadingTemplate = self.app.getJinjaTemplate(
            'ipfssearch-loading.html')

        self.searchQuery = searchQuery
        self.pages = {}
        self.pageCount = 0

        self.ui = ui_ipfssearchw.Ui_IPFSSearchMain()
        self.ui.setupUi(self.mainWidget)

        self.stack = QStackedWidget()
        self.channel = QWebChannel()
        self.handler = Handler(self)
        self.channel.registerObject('ipfssearch', self.handler)

        self.loadingPage = SearchInProgressPage(
            self.loadingTemplate,
            parent=self
        )

        self.resultsPage = SearchResultsPage(
            self.handler,
            self.resultsTemplate,
            self.hitsTemplate,
            self.app.getIpfsConnectionParams(),
            self
        )
        self.resultsPage.setWebChannel(self.channel)
        self.setResultsPage()

        self.ui.comboPages.activated.connect(self.onComboPages)
        self.ui.prevPageButton.clicked.connect(self.onPrevPage)
        self.ui.nextPageButton.clicked.connect(self.onNextPage)
        self.ui.prevPageButton.setIcon(
            self.style().standardIcon(QStyle.SP_MediaSkipBackward))
        self.ui.nextPageButton.setIcon(
            self.style().standardIcon(QStyle.SP_MediaSkipForward))
        self.resultsReceived.connect(self.onResultsRx)

        self.ui.searchQuery.setText(self.searchQuery)

        self.ui.filenameFilter.returnPressed.connect(self.onFiltersChanged)
        self.ui.searchQuery.returnPressed.connect(self.onFiltersChanged)
        self.ui.searchQuery.returnPressed.connect(self.onFiltersChanged)
        self.ui.itemTypeFilter.currentTextChanged.connect(
            self.onFiltersChanged)
        self.ui.contentTypeFilter.currentTextChanged.connect(
            self.onFiltersChanged)
        self.ui.titleFilter.returnPressed.connect(self.onFiltersChanged)

        self.ui.itemTypeFilter.addItem('All')
        self.ui.itemTypeFilter.addItem('Files')
        self.ui.itemTypeFilter.addItem('Directories')

        self.ui.contentTypeFilter.addItem('All')
        self.ui.contentTypeFilter.addItem('Images')
        self.ui.contentTypeFilter.addItem('Videos')
        self.ui.contentTypeFilter.addItem('Code')
        self.ui.contentTypeFilter.addItem('Music')

        for i in range(20, 200, 10):
            self.ui.resultsPerPage.addItem(str(i))

        self.ui.resultsPerPage.setCurrentIndex(0)

        self.lastSeenDays = 365
        self.ui.lastSeenSlider.setTickInterval(1)
        self.ui.lastSeenSlider.setMinimum(1)
        self.ui.lastSeenSlider.setMaximum(365 * 10)
        self.ui.lastSeenSlider.setSliderPosition(self.lastSeenDays)
        self.ui.lastSeenSlider.valueChanged.connect(
            lambda v: self.ui.lastSeenLabel.setText('{0} days'.format(
                str(v))))
        self.ui.lastSeenSlider.sliderReleased.connect(self.onFiltersChanged)

        if self.resultsTemplate and self.searchQuery:
            ensure(self.runSearch(self.searchQuery))
        else:
            self.addErrorPage()

    @property
    def currentPage(self):
        return self.ui.comboPages.currentIndex()

    @property
    def resultsPerPage(self):
        return int(self.ui.resultsPerPage.currentText())

    def setResultsPage(self):
        self.ui.browser.setPage(self.resultsPage)

    def setLoadingPage(self):
        self.ui.browser.setPage(self.loadingPage)

    def onFiltersChanged(self):
        self.pages = {}
        self.pageCount = 0
        self.ui.comboPages.setCurrentIndex(0)
        self.lastSeenDays = self.ui.lastSeenSlider.value()
        self.searchQuery = self.ui.searchQuery.text()
        ensure(self.runSearch(self.searchQuery))

    def getPageData(self, page):
        return self.pages.get(page, None)

    def getPageWidget(self, page):
        pageData = self.getPageData(page)
        if pageData:
            return pageData.get('page', None)

    def disableCombo(self):
        self.ui.comboPages.setEnabled(False)

    def enableCombo(self):
        self.ui.comboPages.setEnabled(True)

    def enableNavArrows(self, enable=True):
        self.ui.prevPageButton.setEnabled(enable)
        self.ui.nextPageButton.setEnabled(enable)

    def onPageChanged(self, idx):
        self.ui.prevPageButton.setEnabled(idx > 0)
        self.ui.nextPageButton.setEnabled(self.pageCount > idx + 1)

    def onPrevPage(self):
        cIdx = self.currentPage
        self.loadPage(cIdx - 1)

    def onNextPage(self):
        cIdx = self.currentPage
        self.loadPage(cIdx + 1)

    def onComboPages(self, idx):
        self.loadPage(idx)

    def loadPage(self, pageNum):
        self.disableCombo()
        pageW = self.getPageWidget(pageNum)

        if not pageW:
            self.app.task(self.runSearchPage, self.searchQuery,
                          pageNum, True)
        else:
            self.displayPage(pageNum)
            self.enableCombo()

    def addEmptyResultsPage(self, searchR):
        page = NoResultsPage(None, parent=self)
        self.ui.browser.setPage(page)

    def addErrorPage(self):
        pass

    def fileFilter(self):
        if self.ui.itemTypeFilter.currentIndex() == 1:
            objType = 'file'
        elif self.ui.itemTypeFilter.currentIndex() == 2:
            objType = 'directory'
        else:
            objType = 'all'
        return objType

    def getFilters(self):
        filters = {
            'references.name': 'test*',

        }

        filenameF = self.ui.filenameFilter.text()
        if len(filenameF) > 0:
            filters['references.name'] = filenameF

        titleF = self.ui.titleFilter.text()
        if len(titleF) > 0:
            filters['references.title'] = titleF

        if self.lastSeenDays in range(0, 31):
            filters['last-seen'] = '>now-{0}d'.format(self.lastSeenDays)
        elif self.lastSeenDays in range(31, 365):
            filters['last-seen'] = '>now-{0}M'.format(
                int(self.lastSeenDays / 30))

        if self.fileFilter() == 'directory':
            filters['_type'] = 'directory'
        if self.fileFilter() == 'file':
            filters['_type'] = 'file'

        return filters

    async def runSearch(self, searchQuery):
        self.setLoadingPage()
        self.ui.labelInfo.setText(iSearching())
        self.ui.comboPages.clear()

        async for sr in ipfssearch.search(searchQuery, preloadPages=0,
                                          filters=self.getFilters(),
                                          sslverify=self.app.sslverify):
            await asyncio.sleep(0)
            pageCount = sr.pageCount

            if pageCount == 0:
                self.addEmptyResultsPage(sr)
                self.enableNavArrows(False)
                self.disableCombo()
                break

            if sr.page == 0 and self.ui.comboPages.count() == 0:
                resCount = sr.results.get('total', iUnknown())
                maxScore = sr.results.get('max_score', iUnknown())
                self.ui.labelInfo.setText(iResultsInfo(resCount, maxScore))

                if pageCount > 256:
                    pageCount = 256

                self.pageCount = pageCount

                for pageNum in range(1, pageCount + 1):
                    self.ui.comboPages.insertItem(pageNum,
                                                  'Page {}'.format(pageNum))

            self.resultsReceived.emit(sr, False)

    async def runSearchPage(self, searchQuery, page, display=False):
        sr = await ipfssearch.getPageResults(searchQuery, page,
                                             filters=self.getFilters(),
                                             sslverify=self.app.sslverify)
        if sr:
            self.resultsReceived.emit(sr, display)

        self.enableCombo()

    def displayPage(self, page):
        pageData = self.getPageData(page)

        if pageData:
            pageW = pageData['page']
            self.handler.results = pageData['results']
            rendered = self.resultsPage.renderHits(pageData['results'])
            self.ui.comboPages.setCurrentIndex(page)
            self.onPageChanged(page)
            self.handler.resultsReadyDom.emit(rendered)
            self.setResultsPage()

    def onResultsRx(self, sr, display):
        log.debug('Results received for page {0}: {1}'.format(sr.page,
            display))
        if sr.page not in self.pages:
            log.debug('Updating results for page {0}'.format(sr.page))
            self.pages[sr.page] = {
                'results': sr,
                'time': int(time.time()),
                'page': self.resultsPage
            }
        else:
            self.pages[sr.page]['time'] = int(time.time())

        if display or sr.page == 0:
            self.displayPage(sr.page)

    def onClose(self):
        return True
