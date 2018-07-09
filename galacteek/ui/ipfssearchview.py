
import asyncio

from PyQt5.QtWidgets import QWidget, QStackedWidget
from PyQt5.QtCore import (QUrl, Qt, pyqtSignal, QRegularExpression,
        QRegularExpressionMatchIterator)
from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QFont

from galacteek.ipfs.cidhelpers import cidValid
from galacteek.ipfs.ipfsops import *
from galacteek.ipfs import ipfssearch

from . import ui_ipfssearchw, ui_ipfssearchwresults
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

def iSearching():
    return QCoreApplication.translate('IPFSSearchResults',
        '<b>Searching ...</b>')

class IPFSSearchResultsW(QWidget):
    def __init__(self, results, parent=None):
        super().__init__(parent)
        self.ui = ui_ipfssearchwresults.Ui_IPFSSearchResults()
        self.ui.setupUi(self)

        self.results = results
        self.searchW = parent

    def render(self):
        pageHtml = '<ul>'
        for hit in self.results.hits:
            hitHash = hit.get('hash', None)

            if hitHash is None or not cidValid(hitHash):
                continue

            hitTitle = hit.get('title', iUnknown())
            hitSize = hit.get('size', iUnknown())
            hitDescr = hit.get('description', '')
            hitType = hit.get('type', iUnknown())
            hitFirstS = hit.get('first-seen', iUnknown())
            pageHtml += '''
                <li>
                    <p>
                    <a href="fs:{0}">{1}</a> (Size {2})

                    <a href="fs:{0}#hashmark"><img src=":/share/icons/hashmarks.png" width="16" height="16"/></a>

                    </p>
                    <ul style="list-style-type: none"><li>
                        {3}
                    </li></ul>
                </li>
            '''.format(joinIpfs(hitHash), hitTitle, hitSize, hitDescr)
        pageHtml += '</ul>'

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

        if fragment == 'hashmark':
            hashV = stripIpfs(path)
            hit = self.results.findByHash(hashV)
            title = hit.get('title', iUnknown()) if hit else ''

            addHashmark(self.searchW.app.marksLocal,
                    path, title)
        else:
            tab = self.searchW.gWindow.addBrowserTab()
            tab.enterUrl(url)

class EmptyResultsW(IPFSSearchResultsW):
    def render(self):
        self.ui.browser.setHtml(iNoResults())

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
    def __init__(self, searchQuery, *args, **kw):
        super(IPFSSearchView, self).__init__(*args, **kw)

        self.searchQuery = searchQuery

        self.ui = ui_ipfssearchw.Ui_IPFSSearchMain()
        self.ui.setupUi(self)

        self.stack = QStackedWidget()
        self.ui.verticalLayout.addWidget(self.stack)
        self.ui.comboPages.activated.connect(self.onComboPages)

        if self.searchQuery:
            self.app.task(self.runSearch, self.searchQuery)

    def disableCombo(self):
        self.ui.comboPages.setEnabled(False)

    def enableCombo(self):
        self.ui.comboPages.setEnabled(True)

    def onComboPages(self, idx):
        self.disableCombo()
        w = self.stack.widget(idx)
        if not w:
            self.app.task(self.runSearchPage, self.searchQuery, idx)
        else:
            self.stack.setCurrentWidget(w)
            self.enableCombo()

    def addEmptyResultsPage(self, searchR):
        page = EmptyResultsW(searchR, self)
        page.render()
        return self.stack.addWidget(page)

    def addResultsPage(self, searchR):
        page = IPFSSearchResultsW(searchR, self)
        page.render()
        return self.stack.addWidget(page)

    async def runSearch(self, searchQuery):
        self.ui.labelInfo.setText(iSearching())
        self.ui.comboPages.clear()
        async for sr in ipfssearch.search(searchQuery, preloadPages=3):
            await asyncio.sleep(0)
            pageCount = sr.pageCount

            if pageCount == 0:
                self.addEmptyResultsPage(sr)
                continue

            if sr.page == 0 and self.ui.comboPages.count() == 0:
                resCount = sr.results.get('total', iUnknown())
                maxScore = sr.results.get('max_score', iUnknown())
                self.ui.labelInfo.setText(iResultsInfo(resCount, maxScore))

                if pageCount > 256:
                    pageCount = 256
                for pageNum in range(1, pageCount+1):
                    self.ui.comboPages.insertItem(pageNum,
                        'Page {}'.format(pageNum))
            await self.processResult(sr)

    async def runSearchPage(self, searchQuery, page):
        sr = await ipfssearch.getPageResults(searchQuery, page)
        if sr:
            idx = await self.processResult(sr)
            self.stack.setCurrentIndex(idx)
        self.enableCombo()

    async def processResult(self, searchR):
        return self.addResultsPage(searchR)
