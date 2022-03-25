import asyncio
import aiohttp
import traceback

from cachetools import cached
from cachetools import TTLCache
from datetime import timedelta

from rdflib import RDF
from rdflib import URIRef
from rdflib import Literal
from rdflib.namespace import XSD

from galacteek import log
from galacteek.services import GService

from galacteek.ipfs import ipfsOp
from galacteek.ipfs.cidhelpers import IPFSPath

from galacteek.core import runningApp
from galacteek.core import utcDatetimeIso
from galacteek.core import utcDatetime
from galacteek.ld import gLdDefaultContext
from galacteek.ld import ipsContextUri
from galacteek.ld.rdf import BaseGraph
from galacteek.ld import ontolochain
from galacteek.ld.rdf.terms import *
from galacteek.ld.sparql import select, where, T, Filter, Prefix


from ..smartqlclient import SmartQLClient
from ..cfg import GraphSemChainSyncConfig


def trackerSubject(curi):
    return f'urn:ontolochain:status:{curi}'


class GraphSemChainSynchronizer:
    def __init__(self, config=None):
        super().__init__()
        self.config = config if config else GraphSemChainSyncConfig()
        self._chainSync = {}

    @property
    def pronto(self):
        return GService.byDotName.get('ld.pronto')

    @ipfsOp
    async def syncFromRemote(self, ipfsop,
                             peerId: str,
                             iri: str,
                             p2pEndpoint: str,
                             graphDescr=None):
        async with ipfsop.p2pDialerFromAddr(p2pEndpoint) as dial:
            if dial.failed:
                return False

            return await self._sync(ipfsop, peerId, iri, dial,
                                    graphDescr=graphDescr)

    @cached(TTLCache(4096, 180))
    def ontoloChainsList(self, hGraph):
        return list(hGraph.subjects(
            predicate=RDF.type,
            object=str(tUriOntoloChain)
        ))

    @cached(TTLCache(1024, 90))
    def ontoloChainsGeoEmittersList(self, hGraph):
        return list(hGraph.subjects(
            predicate=RDF.type,
            object=str(tUriOntoloChainGeoEmitter)
        ))

    @cached(TTLCache(512, 90))
    def ontoloChainsGeoTranspondersList(self, hGraph):
        return list(hGraph.subjects(
            predicate=RDF.type,
            object=str(tUriOntoloChainGeoTransponder)
        ))

    async def _sync(self, ipfsop, peerId, iri, dial, graphDescr=None):
        ipid = await ipfsop.ipid()

        if not ipid:
            log.debug(
                f'Sync with peer {peerId} aborted: no IPID attached')
            return

        graph = self.pronto.graphByUri(iri)
        hGraph = self.pronto.graphHistory

        ourChain = ontolochain.getChainResource(
            hGraph, ontolochain.didMainChainUri(ipid)
        )

        if graph is None or not ipid:
            return

        creds = None
        if graphDescr:
            creds = graphDescr.get('smartqlCredentials')

        if creds:
            auth = aiohttp.BasicAuth(
                creds.get('user', 'smartql'),
                creds.get('password', '')
            )
        else:
            auth = aiohttp.BasicAuth('smartql', 'password')

        smartql = SmartQLClient(dial, auth=auth)

        if 0:
            try:
                await self.syncGeoEntities(
                    hGraph, smartql,
                    await hGraph.rexec(self.ontoloChainsGeoEmittersList),
                    contextName='OntoloChainGeoEmitter'
                )
                await self.syncGeoEntities(
                    hGraph, smartql,
                    await hGraph.rexec(self.ontoloChainsGeoTranspondersList),
                    contextName='OntoloChainGeoTransponder'
                )
            except Exception as err:
                log.debug(
                    f'Sync with {peerId}: failed to fetch geo entities: {err}')

        w = where([
            T(subject='?uri', predicate="a", object="gs:OntoloChain"),
            T(subject='?uri', predicate="ochain:peerId",
              object="?fpeerid"),
        ])

        w.add_filter(filter=Filter(
            f'?uri != <{ourChain.identifier}>'
        ))

        w.add_filter(filter=Filter(
            f'str(?fpeerid) = "{peerId}"'
        ))

        q = select(
            vars=['?uri'],
            w=w
        )
        q.add_prefix(prefix=Prefix(
            prefix='ochain',
            namespace='ips://galacteek.ld/OntoloChain#')
        )

        reply = await smartql.spql.query(str(q))
        chains = []

        try:
            if not reply:
                raise Exception(f'Chains listing {iri}: empty reply')

            for res in reply['results']['bindings']:
                uri = URIRef(res['uri']['value'])

                typecheck = graph.value(
                    subject=uri,
                    predicate=RDF.type
                )

                if not typecheck:
                    gttl = await smartql.resource(
                        str(uri),
                        context='ips://galacteek.ld/OntoloChain'
                    )

                    if not gttl:
                        continue

                    graph.parse(data=gttl, format='ttl')

                subj = trackerSubject(uri)

                res = hGraph.value(
                    predicate='ips://galacteek.ld/ontoloChainTracked',
                    object=uri
                )

                if not res:
                    await hGraph.pullObject({
                        '@context': gLdDefaultContext,
                        '@type': 'OntoloChainTracker',
                        '@id': subj,
                        'ontoloChainTracked': {
                            '@type': 'OntoloChain',
                            '@id': str(uri)
                        }
                    })
                    # chains.append(uri)

                chains.append(uri)
        except Exception as err:
            log.debug(f'OntoloSync: {iri}: error: {err}')

        for curi in chains:
            if curi == ourChain.identifier:
                continue

            tsubj = trackerSubject(curi)

            syncing = self._chainSync.get(curi, False)

            if not syncing:
                self._chainSync[curi] = True
                await self.syncChain(
                    ipid,
                    hGraph,
                    smartql,
                    curi,
                    tsubj
                )
                self._chainSync[curi] = False
            else:
                log.debug(f'OntoloSync: {iri}: already syncing {curi}')

        await smartql.spql.close()

    async def syncGeoEntities(self, graph, smartql, rings,
                              contextName='OntoloChainGeoEmitter'):
        ctxUri = ipsContextUri(contextName)

        w = where([
            T(subject='?uri', predicate="a",
              object=f"gs:{contextName}")
        ])

        for curi in rings:
            w.add_filter(filter=Filter(
                f'?uri != <{curi}>'
            ))

        q = select(
            vars=['?uri'],
            w=w
        )

        reply = await smartql.spql.query(str(q))

        try:
            for res in reply['results']['bindings']:
                uri = URIRef(res['uri']['value'])

                gttl = await smartql.resource(
                    str(uri),
                    context=str(ctxUri)
                )

                if not gttl:
                    continue

                graph.parse(data=gttl, format='ttl')
        except Exception as err:
            traceback.print_exc()
            log.debug(f'Geo rings sync error: {err}')

    async def syncChain(self,
                        ipid,
                        hGraph,
                        smartql,
                        chainUri: URIRef,
                        trackerUri):
        """
        Sync the ontolochain represented by chainUri
        """

        now = utcDatetime()
        tracker = hGraph.resource(trackerUri)

        if not tracker:
            return False

        log.debug(f'OntoloSync: synchronizing chain {chainUri}')

        predCurObj = tUriSemObjCurrent

        dLast, lastSynced = None, tracker.value(p=tUriOntoloChainDateSynced)
        try:
            dLast = lastSynced.toPython()
        except Exception:
            pass
        else:
            log.debug(f'ontoloSync({chainUri}): date last synced: {dLast}')

        if dLast:
            if dLast > now:
                # Force if date is bogus
                delta = timedelta(
                    seconds=self.config.chainSyncIntervalMin * 2)
            else:
                delta = now - dLast

            log.debug(
                f'ontoloSync({chainUri}): last synced: {dLast} '
                f'sync delta: {delta.seconds} secs')

            if delta.seconds < self.config.chainSyncIntervalMin:
                log.debug(
                    f'ontoloSync({chainUri}): delaying sync')
                return

        """
        ourChain = ontolochain.getChainResource(
            hGraph, ontolochain.didMainChainUri(ipid)
        )

        remoteChain = ontolochain.getChainResource(
            hGraph, chainUri
        )
        """

        #
        #
        # Process Verifiable Credentials on the chain
        #
        #
        w = where([
            T(subject='?uri', predicate="a",
              object="gs:OntoloChainVCRecord"),
            T(subject='?uri', predicate="gs:ontoloChain",
              object=f'<{chainUri}>')
        ])

        req = select(
            vars=['?uri'],
            w=w
        )

        async for res in smartql.spql.qBindings(str(req)):
            uri = URIRef(res['uri']['value'])

            processedList = list(hGraph.objects(
                subject=trackerUri,
                predicate=tUriOntoloChainVcProcessed
            ))

            if any(e == uri for e in processedList):
                continue

            gttl = await smartql.resource(
                str(uri),
                context=str(tUriOntoloChainVCRecord),
                timeout=self.config.recordFetchTimeout
            )

            await asyncio.sleep(0.05)

            if await self.processObject(uri, gttl, trace=False):
                # Eat
                async with hGraph.lock:
                    hGraph.parse(data=gttl, format='ttl')

                tracker.add(tUriOntoloChainVcProcessed,
                            uri)
                await asyncio.sleep(0.05)

        # Sync OntoloChainRecords

        for cn in range(0, self.config.recordsPerSync):
            objCount = 0

            w = where([
                T(subject='?uri', predicate="a",
                  object="gs:OntoloChainRecord"),
                T(subject='?uri', predicate="gs:ontoloChain",
                  object=f'<{chainUri}>')
            ])

            curObject = tracker.value(p=predCurObj)

            if curObject:
                oIri = f'<{curObject.identifier}>'
            else:
                oIri = '<urn:ontolorecord:0>'

            log.debug(f'ontoloSync({chainUri}): current is {curObject}')

            w.add_triples(
                triples=[
                    T(subject='?uri', predicate="gs:ontoloBlockPrevious",
                      object=oIri)
                ]
            )

            req = select(
                vars=['?uri'],
                w=w
            )

            async for res in smartql.spql.qBindings(str(req)):
                objCount += 1

                uri = URIRef(res['uri']['value'])

                ex = hGraph.value(subject=uri, predicate=RDF.type)
                if not ex:
                    # Fetch the object record
                    gttl = await smartql.resource(
                        str(uri),
                        context=str(tUriOntoloChainRecord),
                        timeout=self.config.recordFetchTimeout
                    )

                    await asyncio.sleep(0.05)

                    if not gttl:
                        # Can't fetch the record's graph ..
                        log.debug(
                            f'ontoloSync({chainUri}): '
                            f'{uri} record: failed to fetch!')
                        raise Exception(
                            f'{uri}: failed to pull graph from peer')

                    if await self.processObject(uri, gttl, trace=False):
                        # Eat
                        async with hGraph.lock:
                            hGraph.parse(data=gttl, format='ttl')

                        await asyncio.sleep(0.05)
                    else:
                        # Should be fatal here ?
                        log.debug(f'{uri}: failed to process ?!')
                        break
                else:
                    log.debug(f'{uri}: Already in hgraph')

                try:
                    # Lock the hgraph and advance the chain

                    async with hGraph.lock:
                        # Store URI of new record
                        tracker.remove(
                            p=predCurObj
                        )
                        tracker.add(
                            p=predCurObj,
                            o=uri
                        )

                        # Store sync date
                        tracker.remove(
                            p=tUriOntoloChainDateSynced
                        )
                        tracker.add(
                            p=tUriOntoloChainDateSynced,
                            o=Literal(utcDatetimeIso(),
                                      datatype=XSD.dateTime)
                        )
                except Exception as err:
                    log.debug(
                        f'{chainUri}: update to {uri} error: {err}')
                else:
                    log.debug(
                        f'{chainUri}: advanced record to {uri}')

            if objCount == 0:
                log.debug(f'{chainUri}: sync finished')
                break

        return True

    async def processObject(self, uri: URIRef, oTtl: str,
                            trace=True):
        app = runningApp()
        try:
            log.debug(f'Processing {uri}')
            g = BaseGraph().parse(data=oTtl)

            o = g.resource(uri)
            outGraphUri = o.value(p=tUriOntoRecordOutputGraph)
            path = o.value(p=tUriIpfsPath)
            p = IPFSPath(path)

            assert p.valid is True

            await app.s.rdfStore(
                p,
                trace=trace,
                outputGraph=outGraphUri
            )
        except Exception as err:
            log.debug(f'process {uri}: ERROR: {err}')
            return False
        else:
            log.debug(f'process {uri}: SUCCESS')
            return True
