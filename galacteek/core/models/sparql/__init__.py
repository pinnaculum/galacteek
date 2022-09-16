import asyncio

from rdflib.plugins.sparql import prepareQuery

from PyQt5.QtCore import QAbstractListModel
from PyQt5.QtCore import Qt

from galacteek import log
from galacteek import ensure
from galacteek import services
from galacteek.core.models import AbstractModel
from galacteek.core.models import BaseAbstractItem
from galacteek.ld.sparql import querydb
from galacteek.dweb.channels import GAsyncObject


SubjectUriRole = Qt.UserRole


class SparQLQueryRunner(GAsyncObject):
    rq = None

    def __init__(self, graphUri='urn:ipg:i', graph=None,
                 rq=None, bindings=None, debug=False):
        super().__init__()

        self.graphUri = graphUri
        self._graph = graph
        self._results = []
        self._qprepared = {}
        self._varsCount = 0
        self._debug = debug
        self._setup(rqQuery=rq if rq else self.rq,
                    bindings=bindings)

    @property
    def rdf(self):
        return services.getByDotName('ld.pronto')

    @property
    def q0(self):
        return self._qprepared.get('q0')

    @property
    def graph(self):
        if self._graph is not None:
            return self._graph
        elif self.graphUri:
            return self.rdf.graphByUri(self.graphUri)

    def _setup(self, rqQuery: str = None,
               bindings: dict = None):
        if rqQuery is None:
            return
        self._initBindings = bindings

        q = querydb.get(rqQuery)

        if q:
            self.prepare('q0', q)

    def update(self):
        # If a query was already prepared, toast it
        if self.q0:
            ensure(self.graphQueryAsync(self.q0,
                                        bindings=self._initBindings))

    def setGraph(self, graph):
        self._graph = graph
        self.clearModel()

    def clearModel(self):
        self.beginResetModel()
        self._results = []
        self.endResetModel()

    def prepare(self, name, query):
        try:
            q = prepareQuery(query)
        except Exception as err:
            log.debug(str(err))
        else:
            self._qprepared[name] = q

    def graphQuery(self, query, bindings=None):
        ensure(self.graphQueryAsync(query, bindings=bindings))

    async def graphQueryAsync(self, query, bindings=None, setResults=True):
        self._varsCount = 0

        try:
            results = await self.graph.queryAsync(
                query,
                initBindings=bindings
            )
        except Exception as err:
            log.debug(f'Graph query error ocurred: {err}')
            return

        if self._debug:
            log.debug(f'SparQL results: {list(results)}')

        if not setResults:
            return list(results) if results else []

        if results:
            self._varsCount = len(results.vars)

            self.beginResetModel()
            self._results = list(results)
            self.endResetModel()

    def runPreparedQuery(self, queryName, bindings):
        try:
            q = self._qprepared.get(queryName)
            assert q is not None

            results = self.tc(
                self.a_runPreparedQuery, q,
                bindings.toVariant()
            )

            if results:
                self.beginResetModel()
                self._results = results
                self.endResetModel()
        except Exception:
            return None

    async def a_graphQuery(self, app, loop, query):
        """
        Since this coroutines already runs in a separate thread,
        we call graph.query() and not the graph.queryAsync() coro
        """

        try:
            return self.graph.query(query)
        except Exception as err:
            log.debug(f'Graph query error: {err}')

    async def a_runPreparedQuery(self, app, loop, query, bindings):
        try:
            return list(self.graph.query(
                query, initBindings=bindings))
        except Exception as err:
            log.debug(f'Graph prepared query error: {err}')


class SparQLListModel(QAbstractListModel,
                      SparQLQueryRunner):
    def rowCount(self, parent=None):
        try:
            return len(self._results)
        except Exception:
            return 0

    def columnCount(self, parent=None):
        return 1


class SparQLBaseItem(BaseAbstractItem):
    def data(self, column, role):
        try:
            idata = list(self.itemData)[column]

            # TODO: handle rdflib Literals
            return str(idata)
        except Exception:
            return None


class SparQLItemModel(AbstractModel,
                      SparQLQueryRunner):
    def __init__(self, graphUri='urn:ipg:i', graph=None):
        AbstractModel.__init__(self)
        SparQLQueryRunner.__init__(self, graphUri=graphUri, graph=graph)

    async def itemFromResult(self, result, parent):
        return SparQLBaseItem(data=list(result), parent=parent)

    def queryForParent(self, parent):
        # Return the SparQL query + bindings to run for the given parent item
        return None, None

    async def graphBuild(self, query, bindings=None, parentItem=None):
        # Main API: build the tree recursively, asking which sparql
        # query to run for each inserted item

        parent = parentItem if parentItem else self.rootItem

        results = await self.graphQueryAsync(query, bindings=bindings,
                                             setResults=False)
        await asyncio.sleep(0)

        for result in list(results):
            item = await self.itemFromResult(result, parent)

            if item:
                self.beginInsertRows(
                    self.createIndex(parent.row(), 0),
                    parent.childCount(),
                    parent.childCount()
                )
                parent.appendChild(item)
                self.endInsertRows()

                try:
                    q, bds = self.queryForParent(item)
                    if q:
                        await self.graphBuild(q, bindings=bds,
                                              parentItem=item)
                except Exception as err:
                    log.debug(f'graphBuild error: {err}')
                    continue

            await asyncio.sleep(0)
