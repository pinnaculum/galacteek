import asyncio
import async_timeout
import functools
import mimetypes
import weakref
import traceback
from datetime import datetime
from rdflib import RDF

from PyQt5.QtWebEngineWidgets import QWebEnginePage
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebEngineWidgets import QWebEngineSettings
from PyQt5.QtWebChannel import QWebChannel

from PyQt5.QtCore import QObject
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QRegularExpression

from PyQt5.QtCore import QVariant

from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QToolButton
from PyQt5.QtWidgets import QVBoxLayout

from PyQt5.QtGui import QSyntaxHighlighter
from PyQt5.QtGui import QTextCharFormat
from PyQt5.QtGui import QFont

from galacteek import ensure
from galacteek import log
from galacteek import services
from galacteek.config.cmods import ipfs as config_ipfs
from galacteek.ipfs.stat import UnixFsStatInfo
from galacteek.ipfs.cidhelpers import stripIpfs
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ipfs.cidhelpers import cidConvertBase32
from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.wrappers import ipfsOp
from galacteek.ipfs.search import ipfsSearchGen
from galacteek.ipfs.stat import StatInfo
from galacteek.ipfs.mimetype import MIMEType
from galacteek.dweb.render import renderTemplate
from galacteek.core import uid4
from galacteek.core import runningApp
from galacteek.core import html2t

from galacteek.ld.rdf import BaseGraph
from galacteek.ld.rdf.hashmarks import addLdHashmark

from .colors import *
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


class IPFSSearchButton(QToolButton):
    hovered = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.iconNormal = getIcon('search-engine.png')
        self.iconActive = getIcon('search-engine-zoom.png')

    def enterEvent(self, ev):
        self.hovered.emit()


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


class BaseSearchPage(QWebEnginePage):
    pageRendered = pyqtSignal(str)

    def __init__(self, parent, profile=None):
        if profile:
            super(BaseSearchPage, self).__init__(profile, parent)
        else:
            super(BaseSearchPage, self).__init__(parent)

        self.pageRendered.connect(self.onPageRendered)
        self.eventRendered = asyncio.Event()

    def onPageRendered(self, html):
        self.setHtml(html)
        self.eventRendered.set()


class SearchInProgressPage(BaseSearchPage):
    def __init__(self, tmpl, parent=None):
        super(SearchInProgressPage, self).__init__(parent)
        self.template = tmpl
        ensure(self.render())

    async def render(self):
        html = await renderTemplate(self.template, _cache=True)
        if html:
            self.pageRendered.emit(html)


class SearchResultsPageFactory(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.app = QApplication.instance()
        # self.resultsTemplate = self.app.getJinjaTemplate('ipfssearch.html')
        self.resultsTemplate = 'ipfssearch.html'
        self.webProfile = self.app.webProfiles['ipfs']
        self.minVaultSize = 1
        self.pagesVault = weakref.WeakValueDictionary()

    def unvault(self, searchMode='nocontrols'):
        if len(self.pagesVault) <= self.minVaultSize:
            uid = uid4()
            self.pagesVault[uid] = self.getPage(searchMode=searchMode)

    def getPage(self, searchMode='classic'):
        return SearchResultsPage(
            self.webProfile,
            self.resultsTemplate,
            self.app.getIpfsConnectionParams(),
            searchMode=searchMode,
            parent=self
        )


class SearchResultsPage(BaseSearchPage):
    def __init__(
            self,
            profile,
            tmplMain,
            ipfsConnParams,
            searchMode='classic',
            webchannel=None,
            parent=None):
        super(SearchResultsPage, self).__init__(parent, profile=profile)

        self.app = runningApp()

        self.channel = QWebChannel(self)
        self.handler = IPFSSearchHandler(self)
        self.channel.registerObject('ipfssearch', self.handler)
        self.setWebChannel(self.channel)
        self.setBackgroundColor(
            QColor(self.app.theme.colors.webEngineBackground))

        self.settings().setAttribute(
            QWebEngineSettings.FullScreenSupportEnabled,
            True
        )
        self.fullScreenRequested.connect(self.onFullScreenRequest)

        self.app = QApplication.instance()

        self.searchMode = searchMode
        self.template = tmplMain
        self.ipfsConnParams = ipfsConnParams
        ensure(self.render())

    def onFullScreenRequest(self, req):
        req.accept()

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceId):
        log.debug(
            f'JS: level: {level}, line: {lineNumber}, message: {message}'
        )

    async def render(self):
        html = await renderTemplate(self.template,
                                    _cache=True,
                                    _cacheKeyAttrs=['searchMode'],
                                    ipfsConnParams=self.ipfsConnParams,
                                    searchMode=self.searchMode)
        if html:
            self.pageRendered.emit(html)


class IPFSSearchHandler(QObject):
    resultReady = pyqtSignal(str, str, QVariant)
    objectStatAvailable = pyqtSignal(str, object)
    filesStatAvailable = pyqtSignal(str, object)

    # IPFS gateways signals
    availableIpfsGateways = pyqtSignal(QVariant)

    # MIME-types list
    availableMimeTypes = pyqtSignal(QVariant)

    filtersChanged = pyqtSignal()
    clear = pyqtSignal()
    resetForm = pyqtSignal()
    vPageStatus = pyqtSignal(int, int)

    searchTimeout = pyqtSignal(int)
    searchError = pyqtSignal()
    searchStarted = pyqtSignal(str)
    searchComplete = pyqtSignal()
    searchRunning = pyqtSignal(str)
    searchQueryTextChanged = pyqtSignal(str)

    # Minimum triples count to trigger a flush of the buffer graph
    hBufferMinTriplesFlush: int = 512

    def __init__(self, parent):
        super().__init__(parent)

        self.app = QApplication.instance()

        self.vPageCurrent = 0
        self.pagesPerVpage = 1
        self.pageCount = 0
        self.searchQuery = ''

        self.filters = {}
        self._tasks = []
        self._taskSearch = None
        self._cResults = []
        self._hBufferGraph = BaseGraph()
        self._lock = asyncio.Lock()
        self._destroyed = False
        self._outputGraphUri = self.graphUriHashmarksPrivate

        self.app.loop.call_later(
            0.5,
            self._searcherConfigure
        )

        self._bgwTask = ensure(
            self.bufferGraphWatchTask()
        )

        self.destroyed.connect(functools.partial(self.onDestroyed))

    @property
    def prontoService(self):
        return services.getByDotName('ld.pronto')

    @property
    def graphUriHashmarksPrivate(self):
        return 'urn:ipg:i:love:hashmarks:private'

    @property
    def graphUriHashmarksSearchMain(self):
        return 'urn:ipg:i:love:hashmarks:search:main'

    @property
    def outputGraphUri(self):
        return self._outputGraphUri

    @property
    def outputHashmarksGraph(self):
        return self.prontoService.graphByUri(self.outputGraphUri)

    @property
    def vPageCurrent(self):
        return self._vPageCurrent

    @vPageCurrent.setter
    def vPageCurrent(self, page):
        self._vPageCurrent = page

    def onDestroyed(self):
        self._destroyed = True
        self._bgwTask.cancel()

    async def bufferGraphWatchTask(self):
        try:
            while not self._destroyed:
                await asyncio.sleep(10)

                if len(self._hBufferGraph) > self.hBufferMinTriplesFlush:
                    # Flush it to the search graph

                    async with self._lock:
                        await self.outputHashmarksGraph.guardian.mergeReplace(
                            self._hBufferGraph,
                            self.outputHashmarksGraph
                        )

                        # Reset
                        self._hBufferGraph = BaseGraph()

        except asyncio.CancelledError:
            pass
        except Exception:
            traceback.print_exc()

    def _searcherConfigure(self):
        """
        Configure the searcher via the web channel

        Send the available IPFS gateways list via the web channel

        Send the MIME types list
        """

        try:
            gwUrls = config_ipfs.ipfsHttpGatewaysAvailable()
            if gwUrls:
                self.availableIpfsGateways.emit(QVariant(gwUrls))

            self.availableMimeTypes.emit(QVariant(
                sorted(list(mimetypes.types_map.values()))
            ))
        except Exception:
            traceback.print_exc()

    def setSearchWidget(self, widget):
        self.searchW = widget

    def reload(self):
        self.vPageCurrent = 0
        self.filtersChanged.emit()

    def formReset(self):
        self.resetForm.emit()

    def cleanup(self):
        self._cancelTasks()

        self.vPageCurrent = 0
        self.clear.emit()
        self._cResults = []

    def _cancelTasks(self):
        try:
            if self._taskSearch:
                self._taskSearch.cancel()

            for task in self._tasks:
                task.cancel()
                self._tasks.remove(task)
        except Exception:
            log.debug('Failed to cancel search tasks')

        self._tasks = []

    def spawnSearchTask(self):
        self._taskSearch = ensure(self.runSearch(self.searchQuery))

    @pyqtSlot()
    def cancelSearchTasks(self):
        self._cancelTasks()

    @pyqtSlot(str)
    def fetchObject(self, path):
        ensure(self.fetch(path))

    @pyqtSlot(str)
    def pinObject(self, path):
        ensure(self.pin(path))

    @ipfsOp
    async def pin(self, op, path):
        pinner = op.ctx.pinner
        await pinner.queue(path, True, None, qname='ipfs-search')

    @pyqtSlot()
    def previousPage(self):
        if self.vPageCurrent > 0:
            self._cancelTasks()
            self.clear.emit()
            self.vPageCurrent -= 1
            self.spawnSearchTask()

    @pyqtSlot()
    def nextPage(self):
        self._cancelTasks()
        self.clear.emit()
        self.vPageCurrent += 1
        self.spawnSearchTask()

    @pyqtSlot()
    def searchRetry(self):
        self._cancelTasks()
        self.clear.emit()
        self.spawnSearchTask()

    @pyqtSlot(str)
    def openLink(self, path):
        ensure(self.app.resourceOpener.open(path, openingFrom='ipfssearch'))

    @pyqtSlot(str)
    def clipboardInput(self, path):
        if isinstance(path, str):
            self.app.setClipboardText(path)

    def findByHash(self, mHash):
        for result in self._cResults:
            hit = result['hit']
            hitHash = hit.get('hash')

            if not hitHash:
                continue

            if cidConvertBase32(hitHash) == cidConvertBase32(mHash):
                return hit

    @pyqtSlot(str)
    def hashmark(self, path):
        hashV = stripIpfs(path)
        hit = self.findByHash(hashV)

        title = hit.get('title', iUnknown()) if hit else hashV

        if not title:
            return

        descr = hit.get('description', iUnknown()) if hit else ''
        type = hit.get('type') if hit else None
        pinSingle = (type == 'file')
        pinRecursive = (type == 'directory')

        ensure(addHashmarkAsync(
            path,
            title=html2t(title),
            description=descr,
            pin=pinSingle, pinRecursive=pinRecursive))

    @pyqtSlot(str)
    def mplayerQueue(self, path):
        self.app.mainWindow.mediaPlayerQueue(path, playLast=True)

    @pyqtSlot(str)
    def explore(self, path):
        hashV = stripIpfs(path)
        if hashV:
            self.app.mainWindow.explore(hashV)

    @pyqtSlot(str, str, str, str)
    def search(self,
               searchQuery: str,
               lastSeenPeriod: str,
               cType: str,
               mimeType: str):
        self.cleanup()
        self.searchQuery = searchQuery.strip()
        self.searchStarted.emit(self.searchQuery)
        self.filters = self.getFilters(lastSeenPeriod, cType, mimeType)

        self.spawnSearchTask()

    def getFilters(self,
                   lastSeenPeriod: str,
                   cTypeS: str, mimeType: str) -> dict:
        """
        Create the ipfs-search filters based on the UI selectors

        :param str lastSeenPeriod: Last-seen period (e.g: 1M)
        :param str cTypeS: global content filter (e.g: 'images')
        :param str mimeType: exact MIME tyype filter (e.g: 'image/png')
        :rtype: dict
        """
        filters = {}

        cType = cTypeS.lower()

        def exactmt(mtype: str):
            # Exact MIME type filter (use double quotes here)
            return f'"{mtype}"'

        if mimeType != '*':
            # Exact MIME type filter
            filters['metadata.Content-Type'] = exactmt(mimeType)
        elif cType == 'images':
            filters['metadata.Content-Type'] = 'image*'
        elif cType == 'videos':
            filters['metadata.Content-Type'] = 'video*'
        elif cType in ['music', 'audio']:
            filters['metadata.Content-Type'] = 'audio*'
        elif cType == 'text':
            filters['metadata.Content-Type'] = 'text*'
        elif cType == 'webpages':
            filters['metadata.Content-Type'] = 'text/html*'
        elif cType == 'pdf':
            filters['metadata.Content-Type'] = exactmt('application/pdf')

        filters['last-seen'] = f'>now-{lastSeenPeriod}'

        log.debug(f'IPFS search filters: {filters}')

        return filters

    def channelSendIpfsSearchHit(self, ipfsPath: IPFSPath, hit: dict) -> dict:
        hitHash = hit.get('hash')
        mimeType = hit.get('mimetype')
        hitSize = hit.get('size')
        descr = hit.get('description')
        title = hit.get('title')
        score = hit.get('score', 0)

        sizeFormatted = sizeFormat(hitSize if hitSize else 0)

        pHit = {
            'hash': hitHash,
            'path': str(ipfsPath),
            'url': ipfsPath.ipfsUrl,
            'title': html2t(title) if title else iUnknown(),
            'size': hitSize if hitSize else 0,
            'sizeformatted': sizeFormatted,
            'score': score,
            'description': html2t(descr) if descr else None,
            'type': hit.get('type', iUnknown()),
            'first-seen': hit.get('first-seen', None),
            'last-seen': hit.get('last-seen', None)
        }

        if mimeType:
            pHit['mimetype'] = mimeType
        elif pHit['type'] == 'directory':
            pHit['mimetype'] = 'inode/directory'
        else:
            pHit['mimetype'] = 'application/unknown'

        self.resultReady.emit('ipfs-search', hitHash, QVariant(pHit))

        return pHit

    async def sendCyberHit(self, hit):
        hitHash = hit.get('hash')

        ipfsPath = IPFSPath(hitHash)
        if not ipfsPath.valid:
            return

        mType, stat = await self.app.rscAnalyzer(
            ipfsPath,
            fetchExtraMetadata=True
        )

        if not mType or not stat:
            return

        sInfo = StatInfo(stat)

        pHit = {
            'hash': hitHash,
            'path': str(ipfsPath),
            'cyberlink': hit['cyberlink'],
            'url': ipfsPath.ipfsUrl,
            'mimetype': str(mType),
            'title': hitHash,
            'size': sInfo.totalSize,
            'sizeformatted': sizeFormat(sInfo.totalSize),
            'description': None,
            'type': iUnknown(),
            'first-seen': iUnknown()
        }

        self.resultReady.emit('cyber', hitHash, QVariant(pHit))
        self.objectStatAvailable.emit(hitHash, stat)

        await self.graphHashmark(
            IPFSPath(hitHash, autoCidConv=True),
            hit,
            mType,
            stat
        )

    @ipfsOp
    async def graphHashmark(self,
                            ipfsop,
                            iPath: IPFSPath,
                            hit: dict,
                            mType: str,
                            filesStat):
        """
        Store the hashmark in the hashmarks RDF graph
        """

        refs = []

        title = hit.get('title')
        descr = hit.get('description')
        mimetype = hit.get('mimetype')

        if mimetype is None:
            mimeObj = mType
        else:
            mimeObj = MIMEType(mimetype)

        mimeObj = mType

        # Even if the search query was empty, always store an empty
        # string so that the group_concat() works
        kwm = self.searchQuery.split() + ['']

        for ref in hit.get('references', []):
            p = IPFSPath(ref['parent_hash'], autoCidConv=True)

            if not p.valid:
                continue

            refs.append(p.ipfsUrl)

        try:
            dateLastSeen = datetime.strptime(
                hit.get('last-seen'),
                '%Y-%m-%dT%H:%M:%S%z'
            )
        except (TypeError, ValueError):
            dateLastSeen = None

        return await addLdHashmark(
            iPath,
            title if title else iNoTitle(),
            descr=descr,
            size=hit.get('size', 0),
            score=hit.get('score', 0),
            mimeType=mimeObj,
            filesStat=filesStat,
            keywordMatch=kwm,
            referencedBy=refs,
            dateLastSeen=dateLastSeen,
            customOutputGraph=self._hBufferGraph  # write in buffer graph
        )

    async def processIpfsSearchHit(self, ipfsop,
                                   ipfsPath: IPFSPath,
                                   cid: str,
                                   hit: dict,
                                   forceDiscovery=False) -> bool:
        try:
            if forceDiscovery:
                mType, filesStat = await self.app.rscAnalyzer(
                    ipfsPath, fetchExtraMetadata=True,
                    statType=['files']
                )
            else:
                #
                # Fake the unixfs stat (avoids a costly files stat call)
                # running files/stat on every object ultimately just takes
                # too much resources
                #
                if hit['type'] == 'file':
                    filesStat = UnixFsStatInfo({
                        'Hash': hit['hash'],
                        'Type': hit['type'],
                        'Size': hit['size'],
                        'CumulativeSize': hit['size'] + 11  # BC: get rid of it
                    })
                elif hit['type'] == 'directory':
                    filesStat = UnixFsStatInfo({
                        'Hash': hit['hash'],
                        'Type': hit['type'],
                        'Size': 0
                    })
                else:
                    raise ValueError('Unknown hit type')

            self.filesStatAvailable.emit(cid, filesStat.stat)

            await asyncio.sleep(0)

            # could be run in threadpool ?
            stype = self.outputHashmarksGraph.value(
                subject=ipfsPath.ipfsUriRef,
                predicate=RDF.type
            )

            if not stype:
                # Graph it
                await self.graphHashmark(
                    ipfsPath,
                    hit,
                    MIMEType(hit['mimetype']),
                    filesStat
                )

                await asyncio.sleep(0.2)

            return True
        except Exception as err:
            log.debug(f'Process error for {cid}: {err}')
            return False

    @ipfsOp
    async def runSearch(self, ipfsop, searchQuery, timeout=30):
        pageStart = self.vPageCurrent * self.pagesPerVpage
        statusEmitted = False
        gotResults = False

        proxy = self.app.networkProxy()

        try:
            with async_timeout.timeout(timeout):
                async for pageCount, result in ipfsSearchGen(
                        searchQuery,
                        page=pageStart,
                        filters=self.filters,
                        proxyUrl=proxy.url() if proxy else None,
                        sslverify=self.app.sslverify):
                    await asyncio.sleep(0)

                    gotResults = True

                    if not statusEmitted:
                        self.vPageStatus.emit(
                            self.vPageCurrent + 1,
                            pageCount if pageCount > 0 else 1)
                        statusEmitted = True

                    hit = result['hit']

                    self._cResults.append(result)
                    self.searchRunning.emit(searchQuery)

                    if result['engine'] == 'ipfs-search':
                        ipfsPath = IPFSPath(hit['hash'],
                                            autoCidConv=True)
                        if not ipfsPath.valid:
                            continue

                        tsHit = self.channelSendIpfsSearchHit(ipfsPath, hit)

                        await self.processIpfsSearchHit(
                            ipfsop,
                            ipfsPath,
                            hit['hash'],
                            tsHit
                        )

                    await asyncio.sleep(0.1)
        except asyncio.TimeoutError:
            log.debug('Search timeout')
            self.searchTimeout.emit(timeout)
            return False
        except asyncio.CancelledError:
            log.debug('Search cancelled')
            return False
        except Exception:
            traceback.print_exc()
            return False

        if gotResults:
            self.searchComplete.emit()
            return True
        else:
            self.searchError.emit()
            return False


class IPFSSearchView(QWidget):
    titleNeedUpdate = pyqtSignal(str)

    def __init__(self, searchQuery='', parent=None):
        super(IPFSSearchView, self).__init__(parent)
        self.vl = QVBoxLayout()
        self.vl.setSpacing(0)
        self.setLayout(self.vl)
        self.vl.setContentsMargins(0, 0, 0, 0)

        self.tab = parent

        self.app = QApplication.instance()
        self.setAttribute(Qt.WA_DeleteOnClose)

        # Templates
        self.resultsTemplate = self.app.getJinjaTemplate('ipfssearch.html')

        self.browser = QWebEngineView(parent=self)
        self.layout().addWidget(self.browser)

        self.resultsPage = self.app.mainWindow.ipfsSearchPageFactory.getPage()
        self.resultsPage.setParent(self)

        self.resultsPage.handler.searchStarted.connect(
            lambda query: self.titleNeedUpdate.emit(query))

        self.browser.setPage(self.resultsPage)
        self.browser.setFocus(Qt.OtherFocusReason)


class IPFSSearchTab(GalacteekTab):
    def __init__(self, gWindow, query=None, sticky=False):
        super(IPFSSearchTab, self).__init__(gWindow, sticky=sticky)

        self.view = IPFSSearchView(query, parent=self)
        self.view.titleNeedUpdate.connect(
            lambda text: self.setTabName(iIpfsSearchText(text[0:12])))
        self.addToLayout(self.view)
