import asyncio
import otsrdflib
import io

from galacteek import log
from galacteek.services import GService

from galacteek.ipfs import ipfsOp
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.core.ps import makeKeyService

from galacteek.ipfs.pubsub.srvs import graphs as pubsub_graphs
from galacteek.ipfs.pubsub.messages.ld import RDFGraphsExchangeMessage
from galacteek.ld.rdf import IGraph

from rdflib import plugin
from rdflib import URIRef
from rdflib.store import Store

# from .trail import GraphingTrail


class RDFStoresService(GService):
    name = 'graphs'
    rdfIdent = URIRef('g')

    psListenKeys = [
        makeKeyService('ld')
    ]

    @property
    def graphG(self):
        return self._graphs['c0']

    @property
    def historyService(self):
        return GService.byDotName.get('ld.rdf.graphs.history')

    def on_init(self):
        self._graphs = {}

    def graphByUri(self, uri):
        for n, graph in self._graphs.items():
            if str(graph.identifier) == str(uri):
                return graph

    async def on_start(self):
        await super().on_start()

        # self.trailPath = self.rootPath.joinpath('gtrail.json')
        # self.trail = GraphingTrail(self.trailPath)

        self.storesPath = self.rootPath.joinpath('stores').joinpath(
            'devel')
        self.storesPath.mkdir(parents=True, exist_ok=True)

        self.store = plugin.get("SQLAlchemy", Store)(
            identifier=self.rdfIdent
        )

        for cfg in self.serviceConfig.graphs:
            graph = IGraph(
                cfg.name,
                self.storesPath.joinpath(f'igraph_{cfg.name}'),
                self.store,
                identifier=cfg.uri
            )
            graph.open(graph.dbUri, create=True)

            # XXX: NS bind
            graph.iNsBind()

            graph.sCidChanged.connectTo(self.onGraphCidChanged)

            self._graphs[cfg.name] = graph

    async def declareIpfsComponents(self):
        self.psService = pubsub_graphs.RDFBazaarService(
            self.app.ipfsCtx,
            scheduler=self.app.scheduler,
            igraphs=self._graphs
        )
        self.psService.sExch.connectTo(self.onNewExchange)
        await self.ipfsPubsubService(self.psService)

    async def on_stop(self):
        log.debug('RDF stores: closing')

        # self.graphG.destroy(self.dbUri)

        try:
            self.graphG.close()
        except Exception:
            pass
        else:
            log.debug('RDF graph closed')

    @ipfsOp
    async def event_g_services_ld(self, ipfsop, key, message):
        event = message['event']

        if event['type'] == 'DagRdfStorageRequest':
            path = IPFSPath(event['ipfsPath'])
            graphsIris = event.get(
                'outputGraphs',
                [self.graphG.identifier]
            )

            if path.valid:
                result = await self.storeObject(
                    ipfsop, path,
                    graphs=graphsIris
                )

                if result is True:
                    await self.historyService.trace(
                        path, graphsIris
                    )

    async def storeObject(self, ipfsop, path: IPFSPath,
                          graphs=None):
        if isinstance(graphs, list):
            dst = graphs
        else:
            dst = [self.graphG.identifier]

        async with ipfsop.ldOps() as ld:
            objGraph = await ld.dagAsRdf(path)

            if not objGraph:
                return False

            # Purge blank nodes
            # purgeBlank(graph)

            ttl = io.BytesIO()
            objGraph.serialize(ttl, 'ttl')
            ttl.seek(0, 0)

            for uri in dst:
                destGraph = self.graphByUri(uri)
                if destGraph is not None:
                    print('Storing in', uri, destGraph)
                    try:
                        destGraph.parse(ttl)
                    except Exception:
                        continue

        return True

    def ttlSerialize(self):
        ttl = io.BytesIO()
        serializer = otsrdflib.OrderedTurtleSerializer(self.graphG)
        serializer.serialize(ttl)
        ttl.seek(0, 0)
        return ttl.getvalue().decode()

    async def gQuery(self, query, initBindings=None):
        try:
            return await self.app.loop.run_in_executor(
                None,
                self.graphG.query,
                query
            )
        except Exception as err:
            print('query error', str(err))
            pass

    async def onGraphCidChanged(self, name, cid):
        return

        msg = RDFGraphsExchangeMessage.make(self._graphs)
        print('sending', msg)
        await self.psService.send(msg)

    async def onNewExchange(self, eMsg: RDFGraphsExchangeMessage):
        for gd in eMsg.graphs:
            uri = gd['graphUri']
            cid = gd['graphExportCid']

            localG = self.graphByUri(uri)
            print('found', localG, 'for', uri)

            await localG.mergeFromCid(cid)
            print('merged', cid)

    @GService.task
    async def ttlDumpTask(self):
        if not self.app.debugEnabled:
            return

        while not self.should_stop:
            await asyncio.sleep(30)
            await self.graphG.exportTtl()


def serviceCreate(dotPath, config, parent: GService):
    return RDFStoresService(dotPath=dotPath, config=config)
