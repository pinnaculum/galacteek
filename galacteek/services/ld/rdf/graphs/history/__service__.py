import hashlib
import orjson
import asyncio
import json
from aiosparql.client import SPARQLClient

from galacteek import log
from galacteek.services import GService

from galacteek.core import utcDatetimeIso
from galacteek.core import runningApp

from galacteek.ipfs.cidhelpers import IPFSPath

from galacteek.ipfs import ipfsOp
from galacteek.ipfs.p2pservices import sparql as p2psparql
from galacteek.ipfs.pubsub.messages.ld import SparQLHeartbeatMessage

from galacteek.ld import asyncjsonld as jsonld
from galacteek.ld.rdf import BaseGraph
from galacteek.ld.sparql.aioclient import Sparkie


class GraphHistorySynchronizer:
    def __init__(self, hGraph):
        self.hGraph = hGraph

    @ipfsOp
    async def syncFromRemote(self, ipfsop, p2pEndpoint: str):
        async with ipfsop.p2pDialerFromAddr(p2pEndpoint) as dial:
            if dial.failed:
                # Bummer
                return

            await self.sync(ipfsop, dial)

    async def storedObjectsIds(self):
        return self.hGraph.subject_objects(
            predicate='ips://galacteek.ld/ipfsPath'
        )

    def idsMinus(self, ids):
        q = "MINUS {\n"
        for rec in ids:
            q += f'?uri gs:ipfsPath "{rec[1]}" .\n'
        q += "}\n"
        return q

    async def sync(self, ipfsop, dial):
        sparql = Sparkie(dial.httpUrl('/sparql'))

        ids = await self.storedObjectsIds()

        q = """
            PREFIX gs: <ips://galacteek.ld/>
            SELECT ?uri ?dateCreated ?ipfsPath
            WHERE {
                ?uri a gs:GraphTrail ;
                  gs:ipfsPath ?ipfsPath ;
                  gs:dateCreated ?dateCreated .
        """ + self.idsMinus(ids) + """
            }
        """

        reply = await sparql.query(q)

        try:
            for res in reply['results']['bindings']:
                path = IPFSPath(res['ipfsPath']['value'])

                await runningApp().s.rdfStore(path)
        except Exception as err:
            log.debug(f'Sync error: {err}')

        await sparql.close()


class GraphingHistoryService(GService):
    name = 'history'

    @property
    def rdfService(self):
        return GService.byDotName.get('ld.rdf.graphs')

    @property
    def hGraph(self):
        return self.rdfService.graphByUri('urn:ig:g:h0')

    def on_init(self):
        self.trail = None

    async def on_start(self):
        await super().on_start()
        self.synchro = GraphHistorySynchronizer(self.hGraph)

    async def declareIpfsComponents(self):
        self.sqlService = p2psparql.P2PSparQLService(self.hGraph)
        await self.ipfsP2PService(self.sqlService)

        self.rdfService.psService.sSparql.connectTo(
            self.onSparqlStatus)

    async def onSparqlStatus(self, message: SparQLHeartbeatMessage):
        for graph in message.graphs:
            p2pEndpointRaw = graph['sparqlEndpointAddr']

            await self.synchro.syncFromRemote(p2pEndpointRaw)

    async def trace(self, iPath: IPFSPath, graphs: list):
        """
        Main history API (trace an object in the history graph)
        """
        h = hashlib.sha1()
        h.update(iPath.ipfsUrl.encode())
        nodeId = f'io:{h.hexdigest()}'

        doc = {
            '@context': {
                '@vocab': 'ips://galacteek.ld/'
            },
            '@type': 'GraphTrail',
            '@id': nodeId,
            'dateCreated': utcDatetimeIso(),
            'ipfsPath': str(iPath),
            'outputGraphs': graphs
        }

        result = list(self.hGraph.predicate_objects(nodeId))

        if result:
            return

        try:
            ex = await jsonld.expand(doc)

            graph = BaseGraph()

            graph.parse(
                data=orjson.dumps(ex).decode(),
                format='json-ld'
            )

            # Could be optimized using another rdflib method
            self.hGraph.parse(await graph.ttlize())

            ttl = await self.hGraph.ttlize()
            print(ttl.decode())
        except Exception as err:
            log.debug(f'Error recording {iPath} in history: {err}')

    @GService.task
    async def watch(self):
        while not self.should_stop:
            await asyncio.sleep(30)

            msg = SparQLHeartbeatMessage.make()
            msg.graphs.append({
                'graphIri': self.hGraph.identifier,
                'sparqlEndpointAddr': self.sqlService.endpointAddr()
            })

            await self.rdfService.psService.send(msg)


def serviceCreate(dotPath, config, parent: GService):
    return GraphingHistoryService(dotPath=dotPath, config=config)
