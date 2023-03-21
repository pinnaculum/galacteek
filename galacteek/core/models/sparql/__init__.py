import asyncio
import traceback

from rdflib.plugins.sparql import prepareQuery

from PyQt5.QtCore import QAbstractListModel
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QMimeData
from PyQt5.QtCore import QUrl

from galacteek import log
from galacteek import ensure
from galacteek import services
from galacteek.core.models import AbstractModel
from galacteek.core.models import BaseAbstractItem
from galacteek.ld.sparql import querydb

from galacteek.ld.rdf.watch import GraphActivityListener
from galacteek.dweb.channels import GAsyncObject


SubjectUriRole = Qt.UserRole
SubjectRawUriRefRole = Qt.UserRole + 1


class SparQLQueryRunner(GAsyncObject):
    rq = None

    def __init__(self, graphUri='urn:ipg:i', graph=None,
                 rq=None, bindings=None, debug=False):
        super().__init__()

        self.activityListener = GraphActivityListener([graphUri])
        self.activityListener.graphGotMerged.connectTo(self.onGraphGotMerged)

        self.graphUri = graphUri
        self._graph = graph
        self._results = []
        self._initBindings: dict = {}
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

    def rqGet(self, rqName: str) -> str:
        return querydb.get(rqName)

    def bindingsUpdate(self, **bindings) -> None:
        self._initBindings.update(**bindings)

    def _setup(self, rqQuery: str = None,
               bindings: dict = None) -> None:
        if rqQuery is None:
            return
        self._initBindings = bindings

        q = querydb.get(rqQuery)

        if q:
            self.prepare('q0', q)

    def update(self) -> None:
        # If a query was already prepared, toast it

        if self.q0:
            ensure(self.graphQueryAsync(self.q0,
                                        bindings=self._initBindings))

    def setGraph(self, graph) -> None:
        self._graph = graph
        self.clearModel()

    def clearModel(self) -> None:
        self.beginResetModel()
        self._results = []
        self.endResetModel()

    def prepare(self, name, query):
        try:
            q = prepareQuery(query)
        except Exception:
            log.debug(f'Error preparing query: {traceback.format_exc()}')
        else:
            self._qprepared[name] = q

    def graphQuery(self, query, bindings=None):
        ensure(self.graphQueryAsync(query, bindings=bindings))

    async def graphQueryAsync(self, query, bindings=None, setResults=True,
                              queryGraph=None):
        self._varsCount = 0
        graph = queryGraph if queryGraph else self.graph

        try:
            results = await graph.queryAsync(
                query,
                initBindings=bindings
            )
        except Exception as err:
            log.debug(f'Graph query error ocurred: {err}')
            return

        if self._debug:
            log.debug(f'{self.graphUri}: SparQL results: {list(results)}')

        if not setResults:
            return list(results) if results else []

        if results:
            self._varsCount = len(results.vars)

            self.beginResetModel()
            self._results = list(results)
            self.endResetModel()

            self.graph.publishGraphModelUpdateEvent()

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

    async def onGraphGotMerged(self,
                               graphUri: str,
                               graph) -> None:
        pass


class SparQLListModel(QAbstractListModel,
                      SparQLQueryRunner):
    async def onGraphGotMerged(self,
                               graphUri: str,
                               graph) -> None:
        log.warning(
            f'SparQL List model ({self.graphUri}): '
            f'graph {graphUri} received a merge, triggering model update.'
        )
        self.update()

    def rowCount(self, parent=None):
        try:
            return len(self._results)
        except Exception:
            return 0

    def resultGet(self, index):
        return self._results[index.row()]

    def columnCount(self, parent=None):
        return 1

    def rgen(self, *roles):
        for row in range(0, self.rowCount()):
            idx = self.createIndex(row, 0)

            yield tuple([self.data(
                idx,
                role
            ) for role in roles])


class SparQLBaseItem(BaseAbstractItem):
    def data(self, column, role):
        try:
            idata = list(self.itemData)[column]

            # TODO: handle rdflib Literals
            if role == Qt.DisplayRole:
                return str(idata)
            elif role == Qt.ToolTipRole:
                if isinstance(idata, str):
                    return idata
        except Exception:
            return None


class SparQLItemModel(AbstractModel,
                      SparQLQueryRunner):
    """
    SparQL Item model

    Supports recursive tree-building via subqueries for each item
    """

    def __init__(self, graphUri='urn:ipg:i', graph=None,
                 rq=None, bindings=None,
                 columns=['uri']):
        AbstractModel.__init__(self)
        SparQLQueryRunner.__init__(self, graphUri=graphUri, graph=graph,
                                   rq=rq, bindings=bindings)

        self.colList = columns

        self.rootItem = SparQLBaseItem(self.colList)

    async def onGraphUpdated(self, graphUri: str) -> None:
        """
        Changes in the graph
        """
        pass

    async def onGraphGotMerged(self,
                               graphUri: str,
                               graph) -> None:
        """
        Changes in this graph, toast an upgrade of the model by
        pulling changes from the merged graph (and not from the global
        graph, which would incur a major performance hit as the graph grows).
        """

        log.warning(
            f'SparQL Item model ({self.graphUri}): '
            f'graph {graphUri} received a merge, triggering model upgrade. '
            f'Input graph triples count is: {len(graph)}'
        )

        self.upgrade(mergedGraph=graph)

    def clearModel(self) -> None:
        self.rootItem = SparQLBaseItem(self.colList)
        self.modelReset.emit()

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags

        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled

    def mimeData(self, indexes) -> QMimeData:
        # Feed the first URI we find

        mimedata = QMimeData()

        for idx in indexes:
            item = self.getItem(idx)
            if not item:
                continue

            main = item.data(0, SubjectUriRole)

            if isinstance(main, str):
                url = QUrl(main)

                if url.isValid():
                    mimedata.setUrls([url])

                    # Remove if we want to look at sibling indexes
                    break

        return mimedata

    def supportedDragActions(self):
        return Qt.CopyAction | Qt.LinkAction | Qt.MoveAction

    async def itemFromResult(self, result, parent) -> SparQLBaseItem:
        return SparQLBaseItem(data=list(result), parent=parent)

    def queryForParent(self, parent) -> tuple:
        # Return the SparQL query + bindings to run for the given parent item
        return None, None

    async def handleItem(self, item: SparQLBaseItem,
                         parent: SparQLBaseItem) -> None:
        pass

    def insertItem(self,
                   item: SparQLBaseItem,
                   parent: SparQLBaseItem = None) -> None:
        pitem = parent if parent else self.rootItem
        self.beginInsertRows(
            self.createIndex(pitem.row(), 0),
            pitem.childCount(),
            pitem.childCount()
        )
        pitem.appendChild(item)
        self.endInsertRows()

    async def graphBuild(self, query: str,
                         bindings=None,
                         parentItem=None,
                         inputGraph=None,
                         buildMode: str = None) -> None:
        """
        Main API: build the tree recursively, asking which sparql
        query to run for each inserted item
        """

        parent = parentItem if parentItem else self.rootItem
        parentIndex = self.createIndex(parent.row(), 0)

        results = await self.graphQueryAsync(query, bindings=bindings,
                                             queryGraph=inputGraph,
                                             setResults=False)
        await asyncio.sleep(0)

        if not isinstance(results, list):
            return

        for result in list(results):
            if buildMode == 'upgrade' and len(result) > 0:
                """
                Upgrading: check for an item with that URI in the model

                Note: Assuming that "idx 0 in the list" = "Subject URI"
                is handy but we should allow for other scenarios here
                """

                mlist = self.match(
                    parentIndex,
                    SubjectUriRole,
                    str(result[0])
                )

                await asyncio.sleep(0)

                if len(mlist) > 0:
                    continue

            item = await self.itemFromResult(result, parent)

            if item:
                self.insertItem(item, parent)

                try:
                    await self.handleItem(item, parent)

                    q, bds = self.queryForParent(item)
                    if q:
                        await self.graphBuild(q, bindings=bds,
                                              parentItem=item)
                        await asyncio.sleep(0)
                except Exception as err:
                    traceback.print_exc()
                    log.debug(f'graphBuild error: {err}')
                    continue

            await asyncio.sleep(0)

        self.graph.publishGraphModelUpdateEvent()

    def update(self):
        if self.q0:
            ensure(self.graphBuild(self.q0,
                                   bindings=self._initBindings))

    def upgrade(self, mergedGraph=None):
        if self.q0:
            ensure(self.graphBuild(
                self.q0,
                bindings=self._initBindings,
                inputGraph=mergedGraph if mergedGraph else None,
                buildMode='upgrade')
            )
