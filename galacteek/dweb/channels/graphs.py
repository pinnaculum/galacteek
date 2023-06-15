import traceback
import qasync
import os
import os.path

from pathlib import Path
from yarl import URL

from cachetools import TTLCache

from rdflib import Literal
from rdflib import URIRef
from rdflib.namespace import XSD
from rdflib.plugins.sparql import prepareQuery

from SPARQLWrapper import SPARQLWrapper, JSON, RDF

from PyQt5.QtCore import QObject
from PyQt5.QtCore import QAbstractListModel
from PyQt5.QtCore import Qt
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import pyqtProperty
from PyQt5.QtCore import QVariant
from PyQt5.QtCore import QJsonValue

from galacteek import log
from galacteek import services
from galacteek import cached_property
from galacteek import loopTime

from galacteek.core.asynclib import threadExec
from galacteek.core.asynclib.fetch import httpFetch
from galacteek.core.tmpf import TmpDir

from . import GAsyncObject
from . import GOntoloObject
from . import opSlot

# Qt model role names associated with each RDF predicate
rdfPreRoleNames = [
    'articleBody',
    'authorDid',
    'authorNickName',
    'authorFirstName',
    'authorLastName',
    'body',
    'contentUrl',
    'dateCreated',
    'datePublished',
    'dateModified',
    'date',
    'headline',
    'name',
    'firstname',
    'generic',
    'description',
    'language',
    'markdown',
    'lang',
    'section',
    'random',
    'var1',
    'var2',
    'var3',
    'var4',
    'var5',
    'var6',
    'var7',
    'var8',
    'var9',
    'title',
    'uri',
    'url'
]

rdfPreRoles = {}
for idx, role in enumerate(rdfPreRoleNames):
    rdfPreRoles[Qt.UserRole + idx] = role.encode()


class SparQLBase(GAsyncObject):
    @cached_property
    def rdf(self):
        return services.getByDotName('ld.pronto')

    async def a_graphQuery(self, app, loop, query):
        """
        Since this coroutines already runs in a separate thread,
        we call graph.query() and not the graph.queryAsync() coro
        """

        try:
            return list(self.rdf.graphG.query(query))
        except Exception as err:
            log.debug(f'Graph query error: {err}')

    async def a_runPreparedQuery(self, app, loop,
                                 graphUri, query, bindings):
        ltStart = loopTime()
        graph = self.rdf.graphByUri(graphUri)

        try:
            assert graph is not None
            results = graph.query(query, initBindings=bindings)
            aVars = [str(r) for r in results.vars]
        except Exception as err:
            log.debug(f'Graph prepared query error: {err}')
            return None, None
        else:
            duration = loopTime() - ltStart
            self.resultsReady.emit(duration)

            return list(results), aVars


_caches = {}


class SparQLResultsModel(QAbstractListModel,
                         SparQLBase):
    _roles = {}

    noResults = pyqtSignal()
    resultsReady = pyqtSignal(float)
    ready = pyqtSignal()
    bindingsChanged = pyqtSignal()

    def __init__(self, *args, **kw):
        super().__init__()

        self._results = []
        self._qprepared = {}

        self._rolesNames = {}

        self._pCacheSize = 0
        self._pCacheTtl = 3600 * 24
        self._pCacheUse = False
        self._pCacheUsePrefill = False
        self._pQuery = ''
        self._pGraphUri = 'urn:ipg:i'
        self._pPrefixes = {}
        self._pBindings = {}
        self._pStdPrefixes = {}
        self._pIdent = ''

    # Properties
    def _getIdent(self):
        return self._pIdent

    def _setIdent(self, ident: str):
        self._pIdent = ident

    def _getQuery(self):
        return self._pQuery

    def _setQuery(self, q):
        self._pQuery = q

    def _graphUri(self):
        return self._pGraphUri

    def _setGraphUri(self, u):
        self._pGraphUri = u

    def _stdPrefixes(self):
        return self._pStdPrefixes

    def _prefixes(self):
        return self._pPrefixes

    def _setStdPrefixes(self, v):
        try:
            self._pStdPrefixes = v.toVariant()
        except Exception as err:
            log.debug(f'Invalid SparQL std prefixes: {err}')

    def _setPrefixes(self, v):
        try:
            self._pPrefixes = v.toVariant()
        except Exception as err:
            log.debug(f'Invalid SparQL prefixes: {err}')

    def _getCacheSize(self):
        return self._pCacheSize

    def _setCacheSize(self, size: int):
        self._pCacheSize = size

    def _getUseCache(self):
        return self._pCacheUse

    def _setUseCache(self, use):
        self._pCacheUse = use

    def _getUseCachePrefill(self):
        return self._pCacheUsePrefill

    def _setUseCachePrefill(self, use):
        self._pCacheUsePrefill = use

    def _getBindings(self):
        return self._pBindings

    def _setBindings(self, b: QJsonValue):
        try:
            self._pBindings = b.toVariant()
        except Exception:
            pass
        else:
            self.bindingsChanged.emit()

    ident = pyqtProperty(
        "QString", _getIdent, _setIdent)
    query = pyqtProperty(
        "QString", _getQuery, _setQuery)
    graphUri = pyqtProperty(
        "QString", _graphUri, _setGraphUri)
    stdPrefixes = pyqtProperty(
        "QJsonValue", _stdPrefixes, _setStdPrefixes)
    prefixes = pyqtProperty(
        "QJsonValue", _prefixes, _setPrefixes)
    bindings = pyqtProperty(
        "QJsonValue", _getBindings, _setBindings)
    cache = pyqtProperty(
        bool, _getUseCache, _setUseCache)
    cachePrefill = pyqtProperty(
        bool, _getUseCachePrefill, _setUseCachePrefill)
    cacheSize = pyqtProperty(
        int, _getCacheSize, _setCacheSize)

    @property
    def _cache(self):
        global _caches

        _id = self._getIdent()
        _caches.setdefault(_id,
                           TTLCache(
                               self._pCacheSize, self._pCacheTtl))
        return _caches[_id]

    def _prepareQuery(self, name, query):
        try:
            ns = self._pStdPrefixes.copy()
            ns.update(self._pPrefixes)
            q = prepareQuery(query, initNs=ns)
        except Exception as err:
            traceback.print_exc()
            log.debug(str(err))
            return False
        else:
            self._qprepared[name] = q
            return True

    @pyqtSlot()
    def clearModel(self):
        self.beginResetModel()
        self._results = []
        self._rolesNames = []
        self.endResetModel()

    @pyqtSlot()
    def clearCache(self):
        if self._cache is not None:
            self._cache.clear()

    @pyqtSlot(str, str)
    def prepare(self, name, query):
        return self._prepareQuery(name, query)

    @pyqtSlot(str)
    def graphQuery(self, query):
        results = self.tc(self.a_graphQuery, query)
        if results:
            self.beginResetModel()
            self._results = results
            self.endResetModel()

    @qasync.asyncSlot(str, QVariant)
    async def runPreparedQuery(self, queryName, bindings):
        cache = self._cache

        if len(cache) > 0:
            self.beginResetModel()
            # self._results = cache
            self.endResetModel()

            self.resultsReady.emit(0)
            return

        try:
            bv = bindings.toVariant()
            q = self._qprepared.get(queryName)
            assert q is not None

            await threadExec(
                self.__rSyncPreparedQuery,
                self._pGraphUri,
                q,
                bv if bv else self._pBindings
            )
        except Exception:
            traceback.print_exc()
            return None

    def rowCount(self, parent=None, *args, **kwargs):
        if self._cache and len(self._cache) > 0:
            return len(self._cache) - 1

        return len(self._results)

    @pyqtSlot(result=int)
    def count(self):
        return self.rowCount()

    @pyqtSlot(int, result=QVariant)
    def get(self, row: int):
        r = {}
        try:
            for ridx, role in self.roleNames().items():
                r[role.decode()] = self.data(self.index(row, 0), ridx)
        except Exception:
            traceback.print_exc()
            return QVariant(None)
        else:
            return QVariant(r)

    def data(self, QModelIndex, role=None):
        val = None
        row = QModelIndex.row()

        try:
            item = self._results[row]
            roleName = self.roles[role]
            cell = item[roleName.decode()]

            if cell is None:
                return QVariant(None)
            elif isinstance(cell, Literal):
                if cell.datatype in [XSD.dateTime, XSD.date]:
                    # date or datetime: return in isoformat
                    val = cell.toPython().isoformat()
                else:
                    val = cell.value
            elif isinstance(cell, URIRef):
                val = str(cell)
            else:
                raise ValueError(
                    f'Value of type {type(cell)} not supported'
                )

            if val is not None:
                return val
            else:
                return QVariant(None)
        except KeyError as kerr:
            log.warning(f'KeyError on row {row}: {kerr}')
            return QVariant(None)
        except IndexError as ierr:
            log.warning(f'IndexError on row {row}: {ierr}')
            return QVariant(None)
        except ValueError as verr:
            log.warning(f'ValueError on row {row}: {verr}')
            return QVariant(None)

        return QVariant(None)

    def roleIdxFromName(self, name):
        for idx, n in self.roleNames():
            if n == name:
                return idx

    def roleNames(self):
        if self._cache:
            cr = self._cache.get('roles')
            if cr:
                return cr

        pre = {}

        for idx, role in enumerate(self._rolesNames):
            pre[Qt.UserRole + idx] = role.encode()

        return pre

    @property
    def roles(self):
        return self.roleNames()

    @pyqtSlot(result=QVariant)
    def getRolesNames(self):
        return QVariant(self._rolesNames)

    def __rSyncPreparedQuery(self,
                             graphUri, query, bindings):
        # List of schemes that will be treated as RDF uris
        urifySchemes = [
            'did',
            'ipid',
            'ftp',
            'http',
            'https',
            'dweb',
            'ipfs',
            'ipns',
            'ips',
            'i',
            'it',
            'inter'
        ]
        graph = self.rdf.graphByUri(graphUri)
        _bindings = {}

        try:
            assert graph is not None

            # TODO: compute bindings on property setting if possible
            # TOTO: detect urns here ?
            for k, v in bindings.items():
                if isinstance(v, str):
                    u = URL(v)
                    if u.scheme and u.scheme in urifySchemes:
                        _bindings[k] = URIRef(v)
                    else:
                        _bindings[k] = Literal(v)
                elif type(v) in [int, float, bool]:
                    _bindings[k] = Literal(v)
                else:
                    log.warning(f'Unknown binding type for: {k}')

            results = graph.query(query, initBindings=_bindings)
            aVars = [str(r) for r in results.vars]
        except Exception as err:
            traceback.print_exc()
            log.debug(f'Graph prepared query error: {err}')
            return None, None
        else:
            duration = 0

            self.beginResetModel()
            self._results = list(results)
            self._rolesNames = aVars
            self.endResetModel()

            if not results:
                self.noResults.emit()
                return None, None

            if self._pCacheUse:
                self._cache.clear()

                for row, entry in enumerate(results):
                    self._cache[row] = entry

                self._cache['roles'] = self.roleNames()

            self.resultsReady.emit(duration)

            return results, aVars


class ArticlesModel(SparQLResultsModel):
    pass


class MultimediaChannelsModel(SparQLResultsModel):
    pass


class ShoutsModel(SparQLResultsModel):
    pass


class SparQLSingletonResultsModel(QObject):
    pass


class RDFGraphHandler(GOntoloObject):
    @pyqtSlot(str, str, str)
    def tAddLiteral(self, s, p, o):
        self._graph.add((URIRef(s), URIRef(p), Literal(o)))

    @pyqtSlot(str, str, str)
    def tAddUri(self, s, p, o):
        self._graph.add((URIRef(s), URIRef(p), URIRef(o)))

    @pyqtSlot(str, str, result=str)
    def tGetObjFirst(self, s, p):
        for o in self.g().objects(URIRef(s), URIRef(p)):
            return str(o)

        return ''

    @opSlot(str)
    async def ipgRdfMergeFromIpfs(self, ipfsPath: str):
        ipfsop = self.app.ipfsOperatorForLoop()
        graph = self._graph

        try:
            with TmpDir() as dir:
                await ipfsop.client.core.get(
                    ipfsPath, dstdir=dir)

                for fn in os.listdir(dir):
                    fp = Path(dir).joinpath(fn)

                    await self.app.rexec(graph.parse, str(fp))
        except Exception:
            traceback.print_exc()
            return False

        return True

    @opSlot(str, QJsonValue)
    async def ipgRdfMergeFromUrl(self, url: str, options):
        file = None

        try:
            opts = self._dict(options)
            timeout = int(opts.get('timeout', 60))

            file, _s = await httpFetch(url, timeout=timeout)

            if not file:
                log.debug(f'Could not fetch RDF from URL: {url}')
                return False

            await self.app.rexec(self._graph.parse, str(file))
        except Exception as err:
            log.debug(f'Could not merge RDF from URL: {url}: {err}')
            return False

        if file and file.is_file():
            file.unlink()

        return True


class SparQLWrapperResultsModel(SparQLResultsModel):
    """
    Use SparQLWrapper to query a sparql endpoint (dbpedia by default)
    """
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

        self._endpoint = 'https://dbpedia.org/sparql'
        self._pConstructQuery = ''

        self._sparqlw = SPARQLWrapper(self._endpoint)
        self._sparqlw.addDefaultGraph("http://dbpedia.org")

    def _getConstructQuery(self):
        return self._pConstructQuery

    def _setConstructQuery(self, q):
        self._pConstructQuery = q

    constructQuery = pyqtProperty(
        "QString", _getConstructQuery, _setConstructQuery)

    async def a_sparqlWrapperQueryJson(self, app, loop, query, bindings):
        try:
            # emulate bindings
            for k, v in self._pBindings.items():
                query = query.replace(
                    f'?{k}', f'"{v}"'
                )

            self._sparqlw.setQuery(query)
            self._sparqlw.setReturnFormat(JSON)

            ret = self._sparqlw.queryAndConvert()

            assert ret is not None

            self._rolesNames = ret['head']['vars']

            return ret
        except Exception as err:
            log.debug(f'Graph query error: {err}')

    async def a_sparqlWrapperQueryGraph(self, app, loop, query, bindings):
        try:
            # emulate bindings
            for k, v in self._pBindings.items():
                query = query.replace(
                    f'?{k}', f'"{v}"'
                )

            self._sparqlw.setQuery(query)
            self._sparqlw.setReturnFormat(RDF)

            graph = self._sparqlw.queryAndConvert()

            dstGraph = self.rdf.graphByUri(self._pGraphUri)

            assert dstGraph is not None

            await dstGraph.guardian.mergeReplace(
                graph,
                dstGraph
            )

            return True
        except Exception as err:
            log.debug(f'Graph query error: {err}')

    @pyqtSlot(str, QJsonValue)
    def endpointQueryJson(self, query, bindings):
        results = self.tc(self.a_sparqlWrapperQueryJson, query, bindings)

        if results:
            self.beginResetModel()
            self._results = results['results']['bindings']
            self.endResetModel()

            self.resultsReady.emit(0)

    @pyqtSlot(str, QJsonValue)
    def endpointMergeGraph(self, query, bindings):
        self.tc(self.a_sparqlWrapperQueryGraph, query, bindings)

    def rowCount(self, parent=None, *args, **kwargs):
        return len(self._results)

    def data(self, QModelIndex, role=None):
        row = QModelIndex.row()

        try:
            val = None
            item = self._results[row]
            roleName = self.roles[role]

            cell = item[roleName.decode()]

            if cell['type'] == 'uri':
                val = str(cell['value'])
            elif cell['type'] == 'literal':
                # XXX: don't assume str
                val = str(cell['value'])
            elif cell['type'] == 'typed-literal':
                dtype = cell['datatype']

                if dtype == 'http://www.w3.org/2001/XMLSchema#float':
                    val = float(cell['value'])
            else:
                val = None

            if val:
                return val
        except KeyError:
            return ''
        except IndexError:
            return ''

        return None


def createSparQLSingletonProxy(engine, script_engine):
    return SparQLSingletonResultsModel()
