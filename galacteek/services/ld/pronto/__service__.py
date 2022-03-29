import asyncio
import otsrdflib
import io
import random

from galacteek import log
from galacteek.services import GService

from galacteek.ipfs import ipfsOp
from galacteek.ipfs.cidhelpers import IPFSPath

from galacteek.core.asynclib import GThrottler
from galacteek.core.ps import makeKeyService

from galacteek.ipfs.pubsub import TOPIC_LD_PRONTO
from galacteek.ipfs.pubsub.srvs import graphs as pubsub_graphs
from galacteek.ipfs.pubsub.messages.ld import RDFGraphsExchangeMessage
from galacteek.ipfs.pubsub.messages.ld import SparQLHeartbeatMessage
from galacteek.ipfs.p2pservices import smartql as p2psmartql

from galacteek.ld.rdf import IGraph
from galacteek.ld.rdf import IConjunctiveGraph
from galacteek.ld.rdf.guardian import GraphGuardian

from rdflib import plugin
from rdflib import URIRef
from rdflib.store import Store

from galacteek.ld.iri import p2pLibertarianGenUrn
from galacteek.ld.rdf.terms import tUriUsesLibertarianId
from galacteek.ld.rdf.sync import *


class RDFStoresService(GService):
    name = 'graphs'
    rdfIdent = URIRef('g')

    psListenKeys = [
        makeKeyService('ld')
    ]

    @property
    def graphG(self):
        return self.graphByUri('urn:ipg:i')

    @property
    def graphHistory(self):
        return self.graphByUri('urn:ipg:h0')

    @property
    def historyService(self):
        return GService.byDotName.get('ld.pronto.history')

    @property
    def chainEnv(self):
        return self.app.cmdArgs.prontoChainEnv

    @property
    def graphsUrisStrings(self):
        return sorted(
            [str(g.identifier) for n, g in self._graphs.items()]
        )

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

    def on_init(self):
        self._mThrottler = None
        self._mQueue = asyncio.Queue(maxsize=196)
        self._graphs = {}
        self._synchros = {}
        self._guardians = {}
        self._cgraphs = []
        self._cgMain = None

    def defaultThrottler(self):
        return GThrottler(
            rate_limit=10,
            period=60,
            retry_interval=1.0,
            name='pSyncThrottler'
        )

    async def on_start(self):
        await super().on_start()

        tcfg = self.serviceConfig.mSyncThrottler

        try:
            self._mThrottler = GThrottler(
                rate_limit=tcfg.rateLimit,
                period=tcfg.period,
                retry_interval=tcfg.retryInterval,
                name='pSyncThrottler'
            )
        except Exception:
            self._mThrottler = self.defaultThrottler()

        self.storesPath = self.rootPath.joinpath('stores').joinpath(
            self.chainEnv)
        self.storesPath.mkdir(parents=True, exist_ok=True)

        await self.initializeGraphs()

    async def registerRegularGraph(self, uri, cfg):
        self.store = plugin.get("SQLAlchemy", Store)(
            identifier=self.rdfIdent
        )

        rootPath = self.storesPath.joinpath(f'igraph_{cfg.name}')
        rootPath.mkdir(parents=True, exist_ok=True)

        graph = IGraph(
            self.store,
            rootPath,
            name=cfg.name,
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

        rootPath = self.storesPath.joinpath(f'ipcg_{cfg.name}')
        rootPath.mkdir(parents=True, exist_ok=True)
        dbPath = rootPath.joinpath('g_rdf.db')

        cgraph = IConjunctiveGraph(store=store, identifier=uri)
        cgraph.open('sqlite:///{}'.format(str(dbPath)), create=True)
        cgraph.iNsBind()

        subgraphs = cfg.get('subgraphs', {})

        for guri, gcfg in subgraphs.items():
            graph = IGraph(
                store,
                dbPath,
                name=gcfg.name,
                identifier=guri
            )
            graph.iNsBind()

            await self.graphRegServices(gcfg, graph)
            self._graphs[gcfg.name] = graph

        await self.graphRegServices(cfg, cgraph)

        self._graphs[cfg.name] = cgraph

        return cgraph

    async def graphRegServices(self, cfg, graph):
        services = cfg.get('services', {})
        guardianUri = cfg.get('guardian', 'urn:ipg:guardians:goliath')

        guardian = self._guardians.get(guardianUri)
        if guardian:
            graph.setGuardian(guardian)

        for srvtype, cfg in services.items():
            if srvtype == 'sparql':
                try:
                    spconfig = p2psmartql.SparQLServiceConfig(**cfg)
                except Exception:
                    spconfig = p2psmartql.SparQLServiceConfig()

                await self.ipfsP2PService(
                    p2psmartql.P2PSmartQLService(
                        self.chainEnv, graph, config=spconfig)
                )
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

    @ipfsOp
    async def getLibertarianId(self, ipfsop):
        """
        Return a P2P Libertarian ID for this node

        :rtype: URIRef
        """

        nodeIdUriRef = await ipfsop.nodeIdUriRef()

        l0g = self.graphByUri('urn:ipg:l:l0')
        if not nodeIdUriRef or l0g is None:
            return None

        # Find existing ID
        val = l0g.value(
            subject=nodeIdUriRef,
            predicate=tUriUsesLibertarianId
        )

        if not val:
            lid = p2pLibertarianGenUrn(str(nodeIdUriRef))

            l0g.add((
                nodeIdUriRef,
                tUriUsesLibertarianId,
                lid
            ))

            return lid
        else:
            return val

    async def declareIpfsComponents(self):
        self.psService = pubsub_graphs.RDFBazaarService(
            self.app.ipfsCtx,
            TOPIC_LD_PRONTO,
            None,
            scheduler=self.app.scheduler
        )

        self.psService.sExch.connectTo(self.onNewExchange)
        self.psService.sSparql.connectTo(self.onSparqlHeartBeat)

        await self.ipfsPubsubService(self.psService)

    async def onSparqlHeartBeat(self, sender: str,
                                message: SparQLHeartbeatMessage):
        if message.prontoChainEnv != self.chainEnv:
            log.debug(f'{message.prontoChainEnv}: pronto chain mismatch')
            return

        await self._mQueue.put((sender, message))

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
            recordType = event['recordType']
            historyTrace = event['historyTrace']
            chainUri = event.get('chainUri')
            graphIri = event.get(
                'outputGraphIri',
                'urn:ipg:i:i0'
            )

            if path.valid:
                result = await self.storeObject(
                    ipfsop,
                    path,
                    graphs=[graphIri]
                )

                if result is True and historyTrace:
                    await self.historyService.trace(
                        path, graphIri,
                        recordType=recordType,
                        chainUri=chainUri
                    )
            else:
                log.debug(f'{path}: invalid')

    async def storeObject(self, ipfsop,
                          obj,
                          # path: IPFSPath,
                          graphs=None):
        if isinstance(graphs, list):
            dst = graphs
        else:
            dst = [self.graphG.identifier]

        async with ipfsop.ldOps() as ld:
            objGraph = await ld.rdfify(obj)

            if not objGraph:
                return False

            ttl = io.BytesIO()
            objGraph.serialize(ttl, 'ttl')
            ttl.seek(0, 0)

            for uri in dst:
                destGraph = self.graphByUri(uri)

                if destGraph is None:
                    continue

                if not destGraph.guardian:
                    continue

                result = await destGraph.guardian.merge(
                    objGraph, destGraph)

                for so in result:
                    result = await self.storeObject(
                        ipfsop,
                        so,
                        graphs=graphs
                    )

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

    async def heartBeatProcess(self, sender, msg):
        try:
            for graphdef in msg.graphs:
                p2pEndpointRaw = graphdef.get('smartqlEndpointAddr')
                iri = graphdef.get('graphIri')

                if not p2pEndpointRaw or not iri:
                    continue

                graph = self.graphByUri(iri)

                if graph is None or not graph.synchronizer:
                    continue

                await graph.synchronizer.syncFromRemote(
                    sender,
                    iri,
                    p2pEndpointRaw,
                    graphDescr=graphdef,
                    p2pLibertarianId=msg.p2pLibertarianId
                )
        except Exception as err:
            print(err)

    @GService.task
    async def mProcessTask(self):
        if not self._mThrottler:
            self._mThrottler = self.defaultThrottler()

        while not self.should_stop:
            async with self._mThrottler:
                sender, msg = await self._mQueue.get()

                if isinstance(msg, SparQLHeartbeatMessage):
                    await self.heartBeatProcess(sender, msg)

    def p2pSmartQLServices(self):
        for service in reversed(self._children):
            if isinstance(service, p2psmartql.P2PSmartQLService):
                yield service

    def p2pSmartQLServiceByUri(self, uri: URIRef):
        for service in self.p2pSmartQLServices():
            if service.graph.identifier == uri:
                return service

    @GService.task
    async def heartbeatTask(self):
        r = random.Random()

        while not self.should_stop:
            t = r.randint(
                self.serviceConfig.pubsub.heartbeat.intervalMin,
                self.serviceConfig.pubsub.heartbeat.intervalMax
            )
            await asyncio.sleep(t)

            libId = await self.getLibertarianId()

            msg = SparQLHeartbeatMessage.make(
                self.chainEnv,
                libId if libId else ''
            )

            for service in reversed(self._children):
                if not isinstance(service, p2psmartql.P2PSmartQLService):
                    continue

                # Add definition for graph
                # SmartQL http credentials are set by the curve pubsub service
                msg.graphs.append({
                    'graphIri': service.graph.identifier,
                    'smartqlEndpointAddr': service.endpointAddr(),
                    'smartqlCredentials': {
                        'user': 'smartql',
                        'password': ''
                    }
                })

            try:
                await self.psService.send(msg)
            except Exception as err:
                log.debug(f'Could not send smartql heartbeat: {err}')


def serviceCreate(dotPath, config, parent: GService):
    return RDFStoresService(dotPath=dotPath, config=config)
