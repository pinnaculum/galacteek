from rdflib.plugins.sparql import prepareQuery

from PyQt5.QtCore import QAbstractListModel
from PyQt5.QtCore import Qt
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import QVariant

from galacteek import log
from galacteek import services
from galacteek import cached_property
from galacteek.dweb.channels import AsyncChanObject

# Qt model role names associated with each RDF predicate
rdfPreRoleNames = [
    'articleBody',
    'authorDid',
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


class SparQLBase(AsyncChanObject):
    @cached_property
    def rdf(self):
        return services.getByDotName('ld.rdf.graphs')

    @property
    def roles(self):
        return rdfPreRoles

    async def a_graphQuery(self, app, loop, query):
        """
        Since this coroutines already runs in a separate thread,
        we call graph.query() and not the graph.queryAsync() coro
        """

        try:
            return list(self.rdf.graphG.query(query))
        except Exception as err:
            log.debug(f'Graph query error: {err}')

    async def a_runPreparedQuery(self, app, loop, query, bindings):
        graph = self.rdf.graphG

        try:
            return list(graph.query(
                query, initBindings=bindings))
        except Exception as err:
            log.debug(f'Graph prepared query error: {err}')


class SparQLResultsModel(QAbstractListModel,
                         SparQLBase):
    _roles = {}

    def __init__(self):
        super().__init__()
        self._results = []
        self._qprepared = {}

    @pyqtSlot()
    def clearModel(self):
        self.beginResetModel()
        self._results = []
        self.endResetModel()

    @pyqtSlot(str, str)
    def prepare(self, name, query):
        try:
            q = prepareQuery(query)
        except Exception as err:
            log.debug(str(err))
        else:
            self._qprepared[name] = q

    @pyqtSlot(str)
    def graphQuery(self, query):
        results = self.tc(self.a_graphQuery, query)
        if results:
            self.beginResetModel()
            self._results = results
            self.endResetModel()

    @pyqtSlot(str, QVariant)
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

    def rowCount(self, parent=None, *args, **kwargs):
        return len(self._results)

    def data(self, QModelIndex, role=None):
        row = QModelIndex.row()

        try:
            item = self._results[row]
            roleName = self.roles[role]
            return str(item[roleName.decode()])
        except KeyError:
            return ''
        except IndexError:
            return ''

        return None

    def roleNames(self):
        return self.roles


class ArticlesModel(SparQLResultsModel):
    pass


class MultimediaChannelsModel(SparQLResultsModel):
    pass


class ShoutsModel(SparQLResultsModel):
    pass
