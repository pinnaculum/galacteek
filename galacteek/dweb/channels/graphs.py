import traceback
import qasync
import os
from pathlib import Path
from yarl import URL

from cachetools import TTLCache

from rdflib import Literal
from rdflib import URIRef
from rdflib.plugins.sparql import prepareQuery

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

        self._pCacheSize = 128
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
            self._results = []
            self.endResetModel()

            self.resultsReady.emit(0)
            return

        try:
            q = self._qprepared.get(queryName)
            assert q is not None

            await threadExec(
                self.__rSyncPreparedQuery,
                self._pGraphUri,
                q,
                bindings.toVariant()
            )
        except Exception:
            traceback.print_exc()
            return None

    def rowCount(self, parent=None, *args, **kwargs):
        if self._cache and len(self._cache) > 0:
            return len(self._cache)

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
        global _caches

        col = QModelIndex.column()
        row = QModelIndex.row()
        idx = (col, row, role)

        if self._pCacheUse is True:
            ex = self._cache.get(idx)
            if ex:
                return QVariant(ex)
        try:
            val = None
            item = self._results[row]
            roleName = self.roles[role]
            cell = item[roleName.decode()]

            if isinstance(cell, Literal):
                val = str(cell)
            elif isinstance(cell, URIRef):
                val = str(cell)
            else:
                val = str(cell)

            if val:
                if self._pCacheUse and self._cache is not None:
                    self._cache[idx] = val

                return val
        except KeyError:
            traceback.print_exc()
            return ''
        except IndexError:
            traceback.print_exc()
            return ''

        return None

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

    def __rSyncPreparedQuery(self,
                             graphUri, query, bindings):
        graph = self.rdf.graphByUri(graphUri)
        _bindings = {}

        try:
            assert graph is not None

            # TODO: compute bindings on property setting if possible
            for k, v in bindings.items():
                u = URL(v)
                if u.scheme and u.scheme in ['http', 'ips', 'i']:
                    _bindings[k] = URIRef(v)
                else:
                    _bindings[k] = Literal(v)

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
                for cidx in range(0, 1):
                    for eidx, entry in enumerate(results):
                        for ridx, role in self.roleNames().items():
                            idx = (cidx, eidx, ridx)
                            val = self._results[eidx][role.decode()]
                            self._cache[idx] = str(val)

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


def createSparQLSingletonProxy(engine, script_engine):
    return SparQLSingletonResultsModel()
