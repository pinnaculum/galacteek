
import asyncio

from PyQt5.QtWidgets import (QWidget, QTextEdit, QAction, QStackedWidget,
        QVBoxLayout)

from PyQt5.QtCore import QUrl, Qt
from PyQt5.QtCore import pyqtSignal

from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.wrappers import ipfsOp
from galacteek.ipfs import ipfssearch

from . import ui_ipfssearchw, ui_ipfssearchwresults
from .helpers import *
from .widgets import *
from .i18n import *

def iResultsInfo(count, maxScore):
    return QCoreApplication.translate('IPFSSearchResults',
        'Results count: <b>{0}</b> (max score: <b>{1}</b>)').format(
                count, maxScore)

class IPFSSearchResultsW(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = ui_ipfssearchwresults.Ui_IPFSSearchResults()
        self.ui.setupUi(self)

class IPFSSearchView(GalacteekTab):
    def __init__(self, searchQuery, *args, **kw):
        super(IPFSSearchView, self).__init__(*args, **kw)

        self.searchQuery = searchQuery

        self.ui = ui_ipfssearchw.Ui_IPFSSearchMain()
        self.ui.setupUi(self)

        self.stack = QStackedWidget()
        self.ui.verticalLayout.addWidget(self.stack)
        self.ui.comboPages.currentIndexChanged.connect(self.onComboPages)

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
            self.app.task(self.runSearchPage, self.searchQuery, idx+1)
        else:
            self.stack.setCurrentWidget(w)
            self.enableCombo()

    def addPage(self, searchR):
        pageNo = searchR.page

        page = IPFSSearchResultsW(self)
        idx = self.stack.addWidget(page)
        pageHtml = '<ul>'

        for hit in searchR.hits():
            hitHash = hit['hash']
            hitTitle = hit.get('title', iUnknown())
            hitSize = hit.get('size', iUnknown())
            hitDescr = hit.get('description', '')
            hitType = hit.get('type', iUnknown())
            hitFirstS = hit.get('first-seen', iUnknown())
            pageHtml += '''
                <li>
                    <p>
                        <a href="fs:{0}">{1}</a>
                        (Size {2})
                    </p>
                    <ul style="list-style-type: none"><li>
                        {3}
                    </li></ul>
                </li>
            '''.format(joinIpfs(hitHash), hitTitle, hitSize, hitDescr)
        pageHtml += '</ul>'

        def onAnchor(url):
            tab = self.gWindow.addBrowserTab()
            tab.enterUrl(url)

        page.ui.browser.setHtml(pageHtml)
        page.ui.browser.setOpenLinks(False)
        page.ui.browser.setOpenExternalLinks(False)
        page.ui.browser.anchorClicked.connect(onAnchor)
        return idx

    async def runSearch(self, searchQuery):
        self.ui.comboPages.clear()
        async for sr in ipfssearch.search(searchQuery, maxpages=4):
            await asyncio.sleep(0)
            if sr.page == 1 and self.ui.comboPages.count() == 0:
                pageCount = sr.pageCount
                resCount = sr.results.get('total', iUnknown())
                maxScore = sr.results.get('max_score', iUnknown())
                self.ui.labelInfo.setText(iResultsInfo(resCount, maxScore))

                if pageCount > 256:
                    pageCount = 256
                for pageNo in range(1, pageCount):
                    self.ui.comboPages.insertItem(pageNo,
                        'Page {}'.format(pageNo))
            await self.processResult(sr)

    async def runSearchPage(self, searchQuery, page):
        sr = await ipfssearch.searchPageResults(searchQuery, page)
        if sr:
            idx = await self.processResult(sr)
            self.stack.setCurrentIndex(idx)
            self.enableCombo()

    async def processResult(self, searchR):
        return self.addPage(searchR)
