from rdflib.plugins.sparql import prepareQuery

from PyQt5.QtCore import QAbstractListModel
from PyQt5.QtCore import QVariant

from galacteek import log
from galacteek import services
from galacteek.dweb.channels import GAsyncObject


class SparQLListModel(QAbstractListModel,
                      GAsyncObject):
    def __init__(self, graphUri='urn:ipg:i'):
        super().__init__()

        self.graphUri = graphUri
        self._results = []
        self._qprepared = {}

    @property
    def rdf(self):
        return services.getByDotName('ld.pronto')

    @property
    def graph(self):
        return self.rdf.graphByUri(self.graphUri)

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

    def graphQuery(self, query):
        results = self.tc(self.a_graphQuery, query)

        if results:
            self.beginResetModel()
            self._results = results
            self.endResetModel()

    async def graphQueryAsync(self, query):
        try:
            results = list(await self.graph.queryAsync(query))
        except Exception as err:
            log.debug(f'Graph query error: {err}')
            return

        if results:
            self.beginResetModel()
            self._results = results
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

    def rowCount(self, parent=None):
        try:
            return len(self._results)
        except Exception:
            return 0

    def columnCount(self, parent=None):
        return QVariant(None)

    def roleNames(self):
        return {}

    @property
    def roles(self):
        return {}

    async def a_graphQuery(self, app, loop, query):
        """
        Since this coroutines already runs in a separate thread,
        we call graph.query() and not the graph.queryAsync() coro
        """

        try:
            return list(self.graph.query(query))
        except Exception as err:
            log.debug(f'Graph query error: {err}')

    async def a_runPreparedQuery(self, app, loop, query, bindings):
        try:
            return list(self.graph.query(
                query, initBindings=bindings))
        except Exception as err:
            log.debug(f'Graph prepared query error: {err}')
