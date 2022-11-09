import traceback

from PyQt5.QtCore import Qt

from galacteek.ld.rdf import dbpedia
from galacteek.ld.rdf import BaseGraph

from . import SparQLListModel

from . import SubjectUriRole


RdfLabelRole = Qt.UserRole + 10
RdfEnglishLabelRole = RdfLabelRole + 1


class KnowledgeListModel(SparQLListModel):
    def data(self, index, role=None):
        try:
            item = self.resultGet(index)

            if role in [Qt.DisplayRole, RdfLabelRole]:
                return str(item['label'])
            elif role == RdfEnglishLabelRole:
                return str(item['labelEn'])
            elif role == SubjectUriRole:
                return str(item['uri'])
            elif role == Qt.ToolTipRole:
                return str(item.get('desc', item['label']))
        except Exception:
            traceback.print_exc()


async def kgConstructModel(rq: str, *args,
                           db='dbpedia',
                           returnFormat='json'):
    resp = await dbpedia.request(rq, *args,
                                 db=db,
                                 returnFormat=returnFormat)

    if not resp:
        return

    if returnFormat == 'json':
        model = KnowledgeListModel(graph=BaseGraph())

        for binding in resp.bindings:
            res = {}
            for var in resp.variables:
                res[var] = binding[var].value

            model._results.append(res)

        return model
    else:
        graph = resp

        model = KnowledgeListModel(graph=graph)

        # Shouldn't have to do a double query here
        # this is only used with dbpedia right now
        model._results = list(graph.query('''
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT *
            WHERE {
                ?uri rdfs:label ?label .
                ?uri rdfs:label ?labelEn .
            }
        '''))

        return model
