from rdflib.plugins.sparql import prepareQuery

from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import QVariant

from galacteek import services
from galacteek import log

from . import AsyncChanObject


class SparQLInterface(object):
    @property
    def rdfService(self):
        return services.getByDotName('ld.pronto.graphs')

    async def a_sparqlQuery(self, app, loop,
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


class SparQLHandler(AsyncChanObject, SparQLInterface):
    """
    SparQL interface
    """

    @pyqtSlot(str, str, QVariant, result=QVariant)
    def query(self, query, graphIri, bindings):
        try:
            bds = bindings.toVariant()
        except Exception:
            bds = None

        try:
            return self.tc(
                self.a_sparqlQuery, query, graphIri, bds)
        except Exception as err:
            log.debug(f'SparQL query error for {query}: {err}')
            return QVariant([])
