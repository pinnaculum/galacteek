import asyncio
import otsrdflib
import io
import random

from galacteek import log
from galacteek.services import GService

from galacteek.ipfs import ipfsOp
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.core.ps import makeKeyService

from galacteek.ipfs.pubsub.srvs import graphs as pubsub_graphs
from galacteek.ipfs.pubsub.messages.ld import RDFGraphsExchangeMessage
from galacteek.ipfs.pubsub.messages.ld import SparQLHeartbeatMessage
from galacteek.ipfs.p2pservices import smartql as p2psmartql

from galacteek.ld.rdf import IGraph
from galacteek.ld.rdf import IConjunctiveGraph
from galacteek.ld.rdf.guardian import GraphGuardian

from rdflib import plugin
from rdflib import URIRef
from rdflib.graph import Graph
from rdflib.store import Store

from galacteek.services.ld.pronto.graphs.sync import *


class RDFStoresService(GService):
    name = 'graphs'
    rdfIdent = URIRef('g')

    psListenKeys = [
        makeKeyService('ld')
    ]

    @property
    def graphG(self):
        return self.graphByUri('urn:ipg:g:c0')

    @property
    def graphHistory(self):
        return self.graphByUri('urn:ipg:g:h0')

    @property
    def historyService(self):
        return GService.byDotName.get('ld.pronto.graphs.history')

    @property
    def chainEnv(self):
        return self.app.cmdArgs.prontoChainEnv

    def on_init(self):
        self._graphs = {}
        self._synchros = {}
        self._guardians = {}
        self._cgraphs = []
        self._cgMain = None

    def graphByUri(self, uri: str):
        for n, graph in self._graphs.items():
            if str(graph.identifier) == str(uri):
                return graph

        for cgraph in self._cgraphs:
            if str(cgraph.identifier) == str(uri):
                return cgraph

            subg = cgraph.get_context(URIRef(uri))
            if subg is not None:
                return subg

    async def on_start(self):
        await super().on_start()

        self.storesPath = self.rootPath.joinpath('stores').joinpath(
            self.chainEnv)
        self.storesPath.mkdir(parents=True, exist_ok=True)

        await self.initializeGraphs()

    async def registerRegularGraph(self, uri, cfg):
        self.store = plugin.get("SQLAlchemy", Store)(
            identifier=self.rdfIdent
        )

        graph = IGraph(
            cfg.name,
            self.storesPath.joinpath(f'igraph_{cfg.name}'),
            self.store,
            identifier=uri
        )
        graph.open(graph.dbUri, create=True)

        # XXX: NS bind
        graph.iNsBind()

        graph.sCidChanged.connectTo(self.onGraphCidChanged)

        await self.graphRegServices(cfg, graph)

        self._graphs[cfg.name] = graph

    async def registerConjunctive(self, uri, cfg):
        store = plugin.get("SQLAlchemy", Store)(
            identifier=uri
        )

        dbPath = str(
            self.storesPath.joinpath(
                f'ipcgraph_{cfg.name}.db')
        )
        rootPath = self.storesPath.joinpath(f'ipcg_{uri}')
        rootPath.mkdir(parents=True, exist_ok=True)
        dbPath = rootPath.joinpath('g_rdf.db')

        cgraph = IConjunctiveGraph(store=store, identifier=uri)
        cgraph.open('sqlite:///{}'.format(str(dbPath)), create=True)
        cgraph.iNsBind()

        subgraphs = cfg.get('subgraphs', {})

        for guri, gcfg in subgraphs.items():
            graph = Graph(store=store, identifier=URIRef(guri))
            if 0:
                graph = IGraph(
                    gcfg.name,
                    self.storesPath.joinpath(f'igraph_{gcfg.name}'),
                    store,
                    identifier=guri
                )
                graph.iNsBind()

        await self.graphRegServices(cfg, cgraph)

        self._cgraphs.append(cgraph)

        return cgraph

    async def graphRegServices(self, cfg, graph):
        services = cfg.get('services', {})
        guardianUri = cfg.get('guardian', None)

        if guardianUri:
            guardian = self._guardians.get(guardianUri)
            if guardian:
                graph.setGuardian(guardian)

        for srvtype, cfg in services.items():
            if srvtype == 'sparql':
                try:
                    spconfig = p2psmartql.SparQLServiceConfig(**cfg)
                except Exception:
                    spconfig = p2psmartql.SparQLServiceConfig()

                srv = p2psmartql.P2PSmartQLService(
                    self.chainEnv, graph, config=spconfig)
                await self.ipfsP2PService(srv)
            elif srvtype == 'sync':
                use = cfg.get('use', None)
                if use:
                    sync = self._synchros.get(use, None)
                    if sync:
                        graph.synchronizer = sync
            elif synctype == 'export':
                graph.synchronizer = GraphExportSynchronizer(graph)

    async def initializeGraphs(self):
        syncs = self.serviceConfig.get('synchronizers', {})
        for uri, cfg in syncs.items():
            stype = cfg.get('type', 'export')

            if stype in ['export', 'rdfexport']:
                try:
                    cfg = GraphExportSyncConfig(**cfg)
                except Exception:
                    cfg = GraphExportSyncConfig()

                self._synchros[uri] = GraphExportSynchronizer(cfg)
            elif stype in ['sparkie', 'sparql']:
                cfg = GraphSparQLSyncConfig(**cfg)
                self._synchros[uri] = GraphSparQLSynchronizer(cfg)
            elif stype == 'ontolochain':
                synccfg = GraphSemChainSyncConfig(**cfg)
                self._synchros[uri] = GraphSemChainSynchronizer(synccfg)

        guardians = self.serviceConfig.get('guardians', {})
        for uri, cfg in guardians.items():
            g = GraphGuardian(uri, cfg)
            if g.configure():
                self._guardians[uri] = g

        graphs = self.serviceConfig.get('graphs', {})
        for uri, cfg in graphs.items():
            type = cfg.get('type', 'default')

            if type == 'conjunctive':
                await self.registerConjunctive(uri, cfg)
            else:
                await self.registerRegularGraph(uri, cfg)

    async def declareIpfsComponents(self):
        self.psService = pubsub_graphs.RDFBazaarService(
            self.app.ipfsCtx,
            scheduler=self.app.scheduler,
            igraphs=self._graphs
        )
        self.psService.sExch.connectTo(self.onNewExchange)
        self.psService.sSparql.connectTo(self.onSparqlHeartBeat)

        await self.ipfsPubsubService(self.psService)

    async def onSparqlHeartBeat(self, sender: str,
                                message: SparQLHeartbeatMessage):
        if message.prontoChainEnv != self.chainEnv:
            log.debug(f'{message.prontoChainEnv}: pronto chain mismatch')
            return

        for graphdef in message.graphs:
            p2pEndpointRaw = graphdef['smartqlEndpointAddr']
            iri = graphdef['graphIri']

            graph = self.graphByUri(iri)

            if graph is None or not graph.synchronizer:
                continue

            await graph.synchronizer.syncFromRemote(
                sender,
                iri, p2pEndpointRaw,
                graphDescr=graphdef
            )

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
            graphIri = event.get(
                'outputGraphIri',
                'urn:ipg:g:c0'
            )

            if path.valid:
                result = await self.storeObject(
                    ipfsop, path,
                    graphs=[graphIri]
                )

                if result is True:
                    await self.historyService.trace(
                        path, graphIri
                    )
            else:
                log.debug(f'{path}: invalid')

    async def storeObject(self, ipfsop, path: IPFSPath,
                          graphs=None):
        def supgrade(graph, subject: URIRef):
            for rule in graph.tUpRules:
                if rule.reSub.match(str(subject)):
                    return True

            return False

        if isinstance(graphs, list):
            dst = graphs
        else:
            dst = [self.graphG.identifier]

        async with ipfsop.ldOps() as ld:
            objGraph = await ld.dagAsRdf(path)

            if not objGraph:
                return False

            ttl = io.BytesIO()
            objGraph.serialize(ttl, 'ttl')
            ttl.seek(0, 0)

            for uri in dst:
                destGraph = self.graphByUri(uri)

                if destGraph is None:
                    continue

                guardian = destGraph.guardian

                if guardian:
                    await guardian.merge(objGraph, destGraph)

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
        await self.psService.send(msg)

    async def onNewExchange(self, eMsg: RDFGraphsExchangeMessage):
        for gd in eMsg.graphs:
            uri = gd['graphUri']
            cid = gd['graphExportCid']

            localG = self.graphByUri(uri)

            await localG.mergeFromCid(cid)

    @GService.task
    async def heartbeatTask(self):
        r = random.Random()

        while not self.should_stop:
            t = r.randint(
                self.serviceConfig.pubsub.heartbeat.intervalMin,
                self.serviceConfig.pubsub.heartbeat.intervalMax
            )
            await asyncio.sleep(t)

            msg = SparQLHeartbeatMessage.make(self.chainEnv)

            for service in reversed(self._children):
                if not isinstance(service, p2psmartql.P2PSmartQLService):
                    continue

                msg.graphs.append({
                    'graphIri': service.graph.identifier,
                    'smartqlEndpointAddr': service.endpointAddr(),
                    'smartqlCredentials': {
                        'user': service.mwAuth.smartqlUser,
                        'password': service.mwAuth.smartqlPassword
                    }
                })

            await self.psService.send(msg)

    @GService.task
    async def historyTtlDumpTask(self):
        if not self.app.debugEnabled:
            return

        while not self.should_stop:
            await asyncio.sleep(60 * 10)

            await self.graphHistory.exportTtl()


def serviceCreate(dotPath, config, parent: GService):
    return RDFStoresService(dotPath=dotPath, config=config)
