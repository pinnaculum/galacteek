from PyQt5.QtCore import QAbstractListModel
from PyQt5.QtCore import Qt
from PyQt5.QtCore import pyqtSlot

from galacteek import log
from galacteek import services
from galacteek import cached_property
from galacteek.dweb.chanobjects import AsyncChanObject

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


class SparQLResultsModel(QAbstractListModel,
                         AsyncChanObject):
    _roles = {}

    def __init__(self):
        super(SparQLResultsModel, self).__init__()
        self.results = []

    @cached_property
    def rdf(self):
        return services.getByDotName('ld.rdf.stores')

    @property
    def roles(self):
        return rdfPreRoles

    @pyqtSlot()
    def clearModel(self):
        self.beginResetModel()
        self.results = []
        self.endResetModel()

    def rolesFromResults(self, res):
        roles = {}

        for row in res:
            for label in row.labels:
                el = label.encode()
                if el in roles.values():
                    continue

                _id = Qt.UserRole + len(roles)
                roles[_id] = el

        return roles

    @pyqtSlot(str)
    def graphQuery(self, query):
        results = self.tc(self.a_graphQuery, query)
        if results:
            self.beginResetModel()
            self.results = results
            self.endResetModel()

    async def a_graphQuery(self, app, loop, query):
        print('Request is', query)
        graph = self.rdf.graphG

        try:
            return list(graph.query(query))
        except Exception as err:
            log.debug(f'Graph query error: {err}')

    def rowCount(self, parent=None, *args, **kwargs):
        return len(self.results)

    def data(self, QModelIndex, role=None):
        row = QModelIndex.row()

        try:
            item = self.results[row]
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
