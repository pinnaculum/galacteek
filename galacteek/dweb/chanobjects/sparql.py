from rdflib.plugins.sparql import prepareQuery

from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import QVariant

from galacteek import services

from . import AsyncChanObject


class SparQLInterface(object):
    @property
    def rdfService(self):
        return services.getByDotName('ld.rdf.stores')

    async def a_sparqlQuery(self, app, loop, query: str, bindings):
        reply = []
        try:
            q = prepareQuery(query)
            results = self.rdfService.graphG.query(
                q, initBindings=bindings)
        except Exception as err:
            print(str(err))
            return QVariant([])
        else:
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

    @pyqtSlot(str, QVariant, result=QVariant)
    def query(self, query, bindings):
        try:
            return self.tc(
                self.a_sparqlQuery, query, bindings.toVariant())
        except Exception:
            return QVariant([])
