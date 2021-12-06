from rdflib.plugins.sparql import prepareQuery

from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import QVariant
from PyQt5.QtCore import QJsonValue

from galacteek import services
from galacteek import log
from galacteek.ld.rdf import dbpedia

from . import GAsyncObject


class SparQLInterface(object):
    @property
    def rdfService(self):
        return services.getByDotName('ld.pronto')

    async def a_prontoSparqlQuery(self, app, loop,
                                  query: str,
                                  graphIri: str,
                                  bindings):

        reply = []
        try:
            q = prepareQuery(query)
            graph = self.rdfService.graphByUri(graphIri)
            assert graph is not None

            if bindings:
                results = graph.query(
                    q, initBindings=bindings)
            else:
                results = graph.query(q)
        except Exception as err:
            log.debug(f'SparQL query error for {query}: {err}')
            return QVariant([])
        else:
            # Build the QVariant from the results
            for row in results:
                r = {}
                for var in results.vars:
                    r[str(var)] = str(row[var])

                reply.append(r)

            return QVariant(reply)

    async def a_dbpediaQueryJson(self, app, loop,
                                 query: str,
                                 bindings):
        try:
            return QVariant(dbpedia.requestJson(query))
        except Exception as err:
            log.debug(f'SparQL query error for {query}: {err}')
            return QVariant([])


class SparQLHandler(GAsyncObject, SparQLInterface):
    """
    SparQL interface
    """

    @pyqtSlot(str, str, QJsonValue, result=QVariant)
    def prontoQuery(self, query, graphIri, bindings):
        try:
            return self.tc(
                self.a_prontoSparqlQuery,
                query,
                graphIri,
                self._dict(bindings))
        except Exception as err:
            log.debug(f'SparQL query error for {query}: {err}')
            return QVariant([])

    @pyqtSlot(str, QJsonValue, result=QVariant)
    def dbpediaQueryJson(self, query, bindings):
        try:
            return self.tc(
                self.a_dbpediaQueryJson,
                query,
                self._dict(bindings))
        except Exception as err:
            log.debug(f'Dbpedia SparQL query error for {query}: {err}')
            return QVariant([])
