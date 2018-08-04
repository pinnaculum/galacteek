
import asyncio

from PyQt5.QtWidgets import QWidget, QStackedWidget, QStyle
from PyQt5.QtCore import (QUrl, Qt, pyqtSignal, QRegularExpression,
        QRegularExpressionMatchIterator)
from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QFont

from galacteek.ipfs.cidhelpers import cidValid
from galacteek.ipfs.ipfsops import *
from galacteek.ipfs import ipfssearch

from . import ui_ipfssearchw, ui_ipfssearchwresults
from . import ipfsview
from .helpers import *
from .hashmarks import *
from .widgets import *
from .i18n import *

def iResultsInfo(count, maxScore):
    return QCoreApplication.translate('IPFSSearchResults',
        'Results count: <b>{0}</b> (max score: <b>{1}</b>)').format(
                count, maxScore)

def iNoResults():
    return QCoreApplication.translate('IPFSSearchResults',
        '<b>No results found</b>')

def iErrFetching():
    return QCoreApplication.translate('IPFSSearchResults',
        '<b>Error while fetching results</b>')

def iSearching():
    return QCoreApplication.translate('IPFSSearchResults',
        '<b>Searching ...</b>')

class IPFSSearchResultsW(QWidget):
    def __init__(self, results, template, parent=None):
        super().__init__(parent)

        self.ui = ui_ipfssearchwresults.Ui_IPFSSearchResults()
        self.ui.setupUi(self)

        self.results = results
        self.searchW = parent
        self.template = template

    def render(self):
        ctxHits = []

        for hit in self.results.hits:
            hitHash = hit.get('hash', None)

            if hitHash is None or not cidValid(hitHash):
                continue

            ctxHits.append({
                'path':  joinIpfs(hitHash),
                'title': hit.get('title', iUnknown()),
                'size':  hit.get('size', iUnknown()),
                'descr': hit.get('description', ''),
                'type':  hit.get('type', iUnknown()),
                'first-seen': hit.get('first-seen', iUnknown())
            })

        pageHtml = self.template.render(hits=ctxHits)

        self.ui.browser.setHtml(pageHtml)
        self.ui.browser.setOpenLinks(False)
        self.ui.browser.setOpenExternalLinks(False)
        self.ui.browser.anchorClicked.connect(self.onAnchorClicked)

        self.highlighter = Highlighter(self.searchW.searchQuery,
                self.ui.browser.document())

    def onAnchorClicked(self, url):
        fragment = url.fragment()
        path = url.path()

        if not path:
            return

        hashV = stripIpfs(path)

        if fragment == 'hashmark':
            hit = self.results.findByHash(hashV)
            title = hit.get('title', iUnknown()) if hit else ''
            descr = hit.get('description', iUnknown()) if hit else ''

            addHashmark(self.searchW.app.marksLocal,
                    path, title, description=descr)

        elif fragment == 'explore':
            mainW = self.searchW.app.mainWindow
            mainW.exploreHash(hashV)
        else:
            tab = self.searchW.gWindow.addBrowserTab()
            tab.enterUrl(url)

class EmptyResultsW(IPFSSearchResultsW):
    def render(self):
        self.ui.browser.setHtml(iNoResults())

class ErrorPage(IPFSSearchResultsW):
    def render(self):
        self.ui.browser.setHtml(iErrFetching())

class Highlighter(QSyntaxHighlighter):
    """
    Highlights the search query string in the results
    """
    def __init__(self, highStr, doc):
        super().__init__(doc)

        self.highStr =  highStr
        self.fmt = QTextCharFormat()
        self.fmt.setFontWeight(QFont.Bold);
        self.fmt.setForeground(Qt.red);

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

class IPFSSearchView(GalacteekTab):
    resultsReceived = pyqtSignal(ipfssearch.IPFSSearchResults, bool)

    def __init__(self, searchQuery, *args, **kw):
        super(IPFSSearchView, self).__init__(*args, **kw)

        self.searchQuery = searchQuery
        self.pages = {}
        self.pageCount = 0

        self.ui = ui_ipfssearchw.Ui_IPFSSearchMain()
        self.ui.setupUi(self)

        self.stack = QStackedWidget()
        self.ui.verticalLayout.addWidget(self.stack)
        self.ui.comboPages.activated.connect(self.onComboPages)
        self.ui.prevPageButton.clicked.connect(self.onPrevPage)
        self.ui.nextPageButton.clicked.connect(self.onNextPage)
        self.ui.prevPageButton.setIcon(
                self.style().standardIcon(QStyle.SP_MediaSkipBackward))
        self.ui.nextPageButton.setIcon(
                self.style().standardIcon(QStyle.SP_MediaSkipForward))
        self.stack.currentChanged.connect(self.onPageChanged)
        self.resultsReceived.connect(self.onResultsRx)

        self.resultsTempl = self.app.getJinjaTemplate('ipfssearch.html')

        if self.resultsTempl and self.searchQuery:
            self.app.task(self.runSearch, self.searchQuery)
        else:
            self.addErrorPage()

    @property
    def currentPage(self):
        return self.ui.comboPages.currentIndex()

    def getPageData(self, page):
        return self.pages.get(page, None)

    def getPageWidget(self, page):
        pageData = self.pages.get(page, None)
        if pageData:
            return pageData['stackw']

    def disableCombo(self):
        self.ui.comboPages.setEnabled(False)

    def enableCombo(self):
        self.ui.comboPages.setEnabled(True)

    def enableNavArrows(self, enable=True):
        self.ui.prevPageButton.setEnabled(enable)
        self.ui.nextPageButton.setEnabled(enable)

    def onPageChanged(self, idx):
        self.ui.prevPageButton.setEnabled(idx > 0)
        self.ui.nextPageButton.setEnabled(self.pageCount > idx+1)

    def onPrevPage(self):
        cIdx = self.currentPage
        self.loadPage(cIdx-1)

    def onNextPage(self):
        cIdx = self.currentPage
        self.loadPage(cIdx+1)

    def onComboPages(self, idx):
        self.loadPage(idx)

    def loadPage(self, pageNum):
        self.disableCombo()

        pageData = self.getPageData(pageNum)

        if not pageData:
            self.app.task(self.runSearchPage, self.searchQuery,
                pageNum, True)
        else:
            self.displayPage(pageNum)
            self.enableCombo()

    def addEmptyResultsPage(self, searchR):
        page = EmptyResultsW(searchR, self.resultsTempl, parent=self)
        page.render()
        return self.stack.addWidget(page), page

    def addErrorPage(self):
        page = EmptyResultsW(None, self.resultsTempl, parent=self)
        page.render()
        return self.stack.addWidget(page), page

    def addResultsPage(self, searchR):
        page = IPFSSearchResultsW(searchR, self.resultsTempl, parent=self)
        page.render()
        return self.stack.addWidget(page), page

    async def runSearch(self, searchQuery):
        self.ui.labelInfo.setText(iSearching())
        self.ui.comboPages.clear()

        async for sr in ipfssearch.search(searchQuery, preloadPages=3):
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

                for pageNum in range(1, pageCount+1):
                    self.ui.comboPages.insertItem(pageNum,
                        'Page {}'.format(pageNum))

            self.resultsReceived.emit(sr, False)

    async def runSearchPage(self, searchQuery, page, display=False):
        sr = await ipfssearch.getPageResults(searchQuery, page)
        if sr:
            self.resultsReceived.emit(sr, display)

        self.enableCombo()

    def displayPage(self, page):
        pageW = self.getPageWidget(page)
        if pageW:
            self.stack.setCurrentWidget(pageW)
            self.ui.comboPages.setCurrentIndex(page)

    def onResultsRx(self, sr, display):
        idx, page = self.addResultsPage(sr)
        self.pages[sr.page] = {
                'results': sr,
                'stackidx': idx,
                'stackw': page
        }
        if display:
            self.displayPage(sr.page)
