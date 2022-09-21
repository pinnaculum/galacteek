import asyncio
import otsrdflib
import io
import random
import tarfile
import traceback

from pathlib import Path
from yarl import URL
from omegaconf import OmegaConf

from galacteek import log
from galacteek import ensure
from galacteek.services import GService

from galacteek.ipfs import ipfsOp
from galacteek.ipfs.cidhelpers import IPFSPath

from galacteek.core.asynclib import GThrottler
from galacteek.core.asynclib.fetch import assetFetch
from galacteek.core.asynclib.fetch import httpFetch
from galacteek.core.asynclib import asyncReadFile
from galacteek.core.ps import makeKeyService
from galacteek.core import pkgResourcesRscFilename

from galacteek.ipfs.pubsub import TOPIC_LD_PRONTO
from galacteek.ipfs.pubsub.srvs import graphs as pubsub_graphs
from galacteek.ipfs.pubsub.messages.ld import RDFGraphsExchangeMessage
from galacteek.ipfs.pubsub.messages.ld import SparQLHeartbeatMessage
from galacteek.ipfs.p2pservices import smartql as p2psmartql

from galacteek.ld.rdf import GraphURIRef
from galacteek.ld.rdf import BaseGraph
from galacteek.ld.rdf import IGraph
from galacteek.ld.rdf import IConjunctiveGraph
from galacteek.ld.rdf.guardian import GraphGuardian

from rdflib import plugin
from rdflib import URIRef
from rdflib.store import Store

from galacteek.ld.iri import p2pLibertarianGenUrn
from galacteek.ld.iri import urnParse
from galacteek.ld.rdf.terms import tUriUsesLibertarianId
from galacteek.ld.rdf.terms import DATASET
from galacteek.ld.rdf.sync import *

from .__models__ import ProntoServiceModels


class RDFStoresService(GService,
                       ProntoServiceModels):
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
    def graphsUris(self):
        return [GraphURIRef(str(g.identifier))
                for n, g in self._graphs.items()]

    @property
    def graphsUrisStrings(self):
        return sorted(
            [str(g.identifier) for n, g in self._graphs.items()]
        )

    def graphByUri(self, uri: str):
        uriRef = URIRef(uri)

        for n, graph in self._graphs.items():
            if graph.identifier == uriRef:
                return graph

    def cGraphByUri(self, uri: str):
        # Unused
        for cgraph in self._cgraphs:
            if cgraph.identifier == uriRef:
                return cgraph

            subg = cgraph.get_context(uriRef)
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

        self._cfgAgentsPath = pkgResourcesRscFilename(
            __package__,
            'agents.yaml'
        )

    def defaultThrottler(self):
        return GThrottler(
            rate_limit=10,
            period=60,
            retry_interval=1.0,
            name='pSyncThrottler'
        )

    async def on_start(self):
        await super().on_start()

        self._cfgAgents = OmegaConf.load(self._cfgAgentsPath)

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

        await self.initializeSparQLModels()

    def graphRootStoragePath(self, storageName: str):
        return self.storesPath.joinpath(storageName)

    async def registerRegularGraph(self, uri, cfg):
        store = plugin.get("Sleepycat", Store)(
            identifier=uri
        )

        rootPath = self.graphRootStoragePath(f'igraph_{cfg.name}')
        dbPath = rootPath.joinpath('bsddb')
        dbPath.mkdir(parents=True, exist_ok=True)

        graph = IGraph(
            store,
            rootPath,
            name=cfg.name,
            identifier=uri
        )

        graph.open(str(dbPath), create=True)

        # XXX: NS bind
        graph.iNsBind()

        graph.sCidChanged.connectTo(self.onGraphCidChanged)

        await self.graphRegServices(cfg, graph)

        self._graphs[cfg.name] = graph

    async def registerConjunctive(self,
                                  uri: str,
                                  cfg, parentStore=None):
        subgraphs = cfg.get('subgraphs', {})
        useParentStore = cfg.get('useParentStore', False)
        graphBase = cfg.get('defaultBaseGraphUri', None)

        if useParentStore and parentStore:
            store = parentStore
        else:
            store = plugin.get("Sleepycat", Store)(
                identifier=uri
            )

        cgraph = IConjunctiveGraph(
            store=store, identifier=uri,
            default_graph_base=graphBase
        )

        rootPath = self.graphRootStoragePath(f'ipcg_{cfg.name}')
        dbPath = rootPath.joinpath('bsddb')
        dbPath.mkdir(parents=True, exist_ok=True)
        cgraph.open(str(dbPath), create=True)

        cgraph.iNsBind()

        for guri, gcfg in subgraphs.items():
            gtype = gcfg.get('type')

            if not gtype or gtype == 'regular':
                graph = IGraph(
                    store,
                    rootPath,
                    name=gcfg.name,
                    identifier=guri
                )
            elif gtype == 'conjunctive':
                # Recursive
                graph = await self.registerConjunctive(guri, gcfg,
                                                       parentStore=store)
            if graph is not None:
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

        for dseturi, setcfg in cfg.get('datasets', {}).items():
            url = setcfg.get('url')
            format = setcfg.get('format', 'gdsa1')

            if not isinstance(url, str):
                continue

            csUrl = setcfg.get(
                'checksumUrl',
                f'{url}.sha512'
            )

            dsrevurl = setcfg.get(
                'revisionUrl',
                f'{url}.dsrev'
            )

            upgradeStrategy = setcfg.get(
                'upgradeStrategy',
                'mergeReplace'
            )

            if not urnParse(dseturi):
                continue

            source = URL(url)
            if not source.name.endswith('.tar.gz'):
                continue

            ensure(self.graphDataSetPullTask(
                graph,
                URIRef(dseturi),
                source,
                URL(csUrl) if csUrl else None,
                URL(dsrevurl) if dsrevurl else None,
                format=format,
                upgradeStrategy=upgradeStrategy
            ))

    async def graphDataSetPullTask(self,
                                   graph,
                                   opSubject: URIRef,
                                   url: URL,
                                   checksumUrl: URL,
                                   revisionUrl: URL,
                                   upgradeStrategy: str = 'mergeReplace',
                                   format=None):
        sleepAlreadyDone = 60
        sleepAfterUpdate = 60 * 5
        sleepInvalidDs = 60 * 10
        sleepCannotFetch = 60 * 5

        async def dsTarProcess(ograph, tarfp: Path):
            lastRevision = ograph.value(
                subject=opSubject,
                predicate=DATASET.revision
            )

            try:
                tar = tarfile.open(str(tarfp))
                names = tar.getnames()
                g = BaseGraph()

                for name in names:
                    if not name.endswith('.nt'):
                        continue

                    try:
                        file = tar.extractfile(name)
                        g.parse(file)
                    except Exception as err:
                        log.debug(f'dsProcess: {name} failed: {err}')
                        continue

                tar.close()

                thisRevision = g.value(
                    subject=opSubject,
                    predicate=DATASET.revision
                )

                if lastRevision and thisRevision == lastRevision and 0:
                    log.debug(f'Dataset {opSubject}: same revision')
                    return False

                if upgradeStrategy == 'mergeReplace':
                    await ograph.guardian.mergeReplace(
                        g,
                        ograph
                    )
                elif upgradeStrategy == 'replace':
                    for s, p, o in ograph:
                        ograph.remove((s, p, o))

                    await ograph.guardian.mergeReplace(
                        g,
                        ograph
                    )
            except Exception:
                traceback.print_exc()
                pass
            else:
                ograph.add((
                    opSubject,
                    DATASET.processedRevision,
                    thisRevision
                ))

                log.info(
                    f'Dataset {opSubject}: upgraded to '
                    f'revision: {thisRevision}'
                )
                return True

        while not self.should_stop:
            fp = None

            try:
                checksum = None
                remoteRev = None

                lastProcessedRev = graph.value(
                    subject=opSubject,
                    predicate=DATASET.processedRevision
                )

                if revisionUrl:
                    rfp, _s = await httpFetch(revisionUrl)
                    if rfp:
                        contents = await asyncReadFile(
                            str(rfp), mode='rt')
                        if contents:
                            remoteRev = contents.split()[0]

                        rfp.unlink()

                if lastProcessedRev and remoteRev == str(lastProcessedRev):
                    # Already processed
                    log.debug(f'Dataset {url}: already processed '
                              f'revision: {remoteRev}')

                    await asyncio.sleep(sleepAlreadyDone)
                    continue

                if checksumUrl:
                    cfp, _s = await httpFetch(checksumUrl)
                    if cfp:
                        contents = await asyncReadFile(
                            str(cfp), mode='rt')
                        if contents:
                            checksum = contents.split()[0]

                        cfp.unlink()

                # Use assetFetch (will pull from IPFS if the redirection
                # points to an IPFS file)
                fp, _sum = await assetFetch(url)
                if not fp:
                    log.warning(f'Dataset {url}: failed to retrieve')
                    await asyncio.sleep(sleepCannotFetch)
                    continue

                if checksumUrl and _sum != checksum:
                    log.warning(f'Dataset {url}: checksum mismatch!')
                    await asyncio.sleep(sleepInvalidDs)
                    continue

                if fp.name.endswith('.tar.gz'):
                    if await dsTarProcess(graph, fp):
                        if fp and fp.is_file():
                            fp.unlink()

                        await asyncio.sleep(sleepAfterUpdate)
                else:
                    log.debug('Unsupported dataset format')
                    await asyncio.sleep(60)
                    continue
            except Exception:
                traceback.print_exc()

                if fp and fp.is_file():
                    fp.unlink()

            await asyncio.sleep(30)

    async def initializeGraphs(self):
        # syncs = self.serviceConfig.get('synchronizers', {})
        syncs = self._cfgAgents.get('synchronizers', {})

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

        # guardians = self.serviceConfig.get('guardians', {})
        guardians = self._cfgAgents.get('guardians', {})

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

        for gn, graph in self._graphs.items():
            try:
                graph.close()
            except Exception as err:
                log.debug(f'RDF graphs close error: {err}')
            else:
                log.debug('RDF graphs closed')

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
                        chainUri=URIRef(chainUri) if chainUri else None
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
        except Exception:
            traceback.print_exc()

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
