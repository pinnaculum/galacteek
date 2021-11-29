import zlib
import attr
import aiohttp
import async_timeout

from cachetools import cached
from cachetools import TTLCache

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
from galacteek.ld.rdf import BaseGraph
from galacteek.ld.rdf.terms import *
from galacteek.ld.sparql.aioclient import Sparkie
from galacteek.ld.sparql import select, where, T, Filter


@attr.s(auto_attribs=True)
class GraphExportSyncConfig:
    type: str = 'rdfexport'
    format: str = 'ttl'
    compression: str = 'gzip'


@attr.s(auto_attribs=True)
class GraphSparQLSyncConfig:
    type: str = 'sparkie'
    run: list = []


@attr.s(auto_attribs=True)
class GraphSemChainSyncConfig:
    type: str = 'ontolochain'
    recordsPerSync: int = 256
    recordFetchTimeout: int = 30
    syncIntervalMin: int = 60


class SmartQLClient:
    def __init__(self, dialCtx, auth: aiohttp.BasicAuth = None):
        self.dial = dialCtx

        self.auth = auth if auth else aiohttp.BasicAuth('smartql', 'default')
        self.spql = Sparkie(self.dial.httpUrl('/sparql'), auth=self.auth)

    async def resource(self, iri, context=None, timeout=60):
        graph = BaseGraph()
        url = self.dial.httpUrl(f'/resource/{iri}/graph')

        headers = {
            'Accept': 'application/x-turtle'
        }

        params = {
            'fmt': 'ttl',
            'context': context
        }

        try:
            with async_timeout.timeout(timeout):
                async with aiohttp.ClientSession(headers=headers,
                                                 auth=self.auth) as session:
                    async with session.get(url, params=params) as resp:
                        data = await resp.read()
                        assert data is not None

                        ctype = resp.headers.get('Content-Type')

                        if ctype == 'application/gzip':
                            gdata = zlib.decompress(data).decode()
                        else:
                            gdata = data.decode()

                        graph.parse(data=gdata, format=params['fmt'])
        except Exception as err:
            log.debug(f'resource graph pull error for {iri}: {err}')
        else:
            log.debug(f'resource graph pull for {iri}: success')
            return gdata


class GraphExportSynchronizer:
    def __init__(self, config=None):
        self.config = config if config else GraphExportSyncConfig()

    @ipfsOp
    async def syncFromRemote(self, ipfsop,
                             peerId: str,
                             iri: str, p2pEndpoint: str,
                             graphDescr=None):
        async with ipfsop.p2pDialerFromAddr(p2pEndpoint) as dial:
            if dial.failed:
                return False

            return await self.syncFromExport(ipfsop, iri, dial,
                                             graphDescr=graphDescr)

    async def syncFromExport(self, ipfsop, iri, dial, graphDescr=None):
        rdfService = GService.byDotName.get('ld.pronto')
        graph = rdfService.graphByUri(iri)

        if graph is None:
            return

        url = dial.httpUrl('/export')
        params = {
            'fmt': self.config.format,
            'compression': self.config.compression
        }

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

        # smartql = SmartQLClient(dial, auth=auth)

        try:
            async with aiohttp.ClientSession(auth=auth) as session:
                async with session.get(url, params=params) as resp:
                    data = await resp.read()
                    assert data is not None

                    ctype = resp.headers.get('Content-Type')

                    if ctype == 'application/gzip':
                        gdata = zlib.decompress(data).decode()
                    else:
                        gdata = data.decode()

                    graph.parse(data=gdata, format=params['fmt'])
        except Exception as err:
            log.debug(f'Graph export sync error for {iri}: {err}')


class GraphSparQLSynchronizer:
    def __init__(self, config=None):
        self.config = config if config else GraphSparQLSyncConfig()

    @ipfsOp
    async def syncFromRemote(self, ipfsop,
                             peerId: str,
                             iri: str,
                             p2pEndpoint: str,
                             graphDescr=None):
        async with ipfsop.p2pDialerFromAddr(p2pEndpoint) as dial:
            if dial.failed:
                return False

            return await self.syncFromExport(ipfsop, iri, dial)

    async def syncFromExport(self, ipfsop, iri, dial):
        rdfService = GService.byDotName.get('ld.pronto')
        graph = rdfService.graphByUri(iri)

        if graph is None:
            return


class GraphSemChainSynchronizer:
    def __init__(self, config=None):
        super().__init__()
        self.config = config if config else GraphSemChainSyncConfig()
        self._chainSync = {}

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

    @cached(TTLCache(3, 90))
    def ontoloChainsList(self, hGraph):
        return list(hGraph.subjects(
            predicate=RDF.type,
            object=str(tUriOntoloChain)
        ))

    async def _sync(self, ipfsop, peerId, iri, dial, graphDescr=None):
        curProfile = ipfsop.ctx.currentProfile
        ipid = await curProfile.userInfo.ipIdentifier()
        rdfService = GService.byDotName.get('ld.pronto')
        graph = rdfService.graphByUri(iri)

        hGraph = rdfService.graphHistory
        # XXX
        # hGraph = graph

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

        chains = await hGraph.rexec(self.ontoloChainsList)

        w = where([
            T(subject='?uri', predicate="a", object="gs:OntoloChain")
        ])

        for curi in chains:
            w.add_filter(filter=Filter(
                f'?uri != <{curi}>'
            ))

        q = select(
            vars=['?uri'],
            w=w
        )

        reply = await smartql.spql.query(str(q))

        try:
            if not reply:
                raise Exception(f'Chains listing {iri}: empty reply')

            for res in reply['results']['bindings']:
                uri = URIRef(res['uri']['value'])

                gttl = await smartql.resource(
                    str(uri),
                    context='ips://galacteek.ld/OntoloChain'
                )

                if not gttl:
                    continue

                graph.parse(data=gttl, format='ttl')

                subj = f'urn:ontolochain:status:{uri}'

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
                    chains.append(uri)
        except Exception as err:
            log.debug(f'OntoloSync: {iri}: error: {err}')

        for curi in chains:
            tsubj = f'urn:ontolochain:status:{curi}'

            syncing = self._chainSync.get(curi, False)

            if not syncing:
                log.debug(f'OntoloSync: {iri}: synchronizing chain {curi}')

                self._chainSync[curi] = True
                await self.syncChain(
                    hGraph,
                    smartql,
                    curi,
                    tsubj
                )
                self._chainSync[curi] = False
            else:
                log.debug(f'OntoloSync: {iri}: already syncing {curi}')

        await smartql.spql.close()

    async def syncChain(self, hGraph,
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

        predCurObj = tUriSemObjCurrent

        dLast, lastSynced = None, tracker.value(p=tUriOntoloChainDateSynced)
        try:
            dLast = lastSynced.toPython()
        except Exception:
            pass
        else:
            log.debug(f'ontoloSync({chainUri}): date last synced: {dLast}')

        if dLast:
            # Calculate delta
            # TODO: prevent oversync here
            delta = now - dLast
            log.debug(
                f'ontoloSync({chainUri}): sync delta: {delta.seconds} secs')

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

            if await self.processObject(uri, gttl, trace=False):
                # Eat
                async with hGraph.lock:
                    hGraph.parse(data=gttl, format='ttl')

                tracker.add(tUriOntoloChainVcProcessed,
                            uri)

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
                    else:
                        # Should be fatal here ?
                        log.debug(f'{uri}: failed to process ?!')
                        break
                else:
                    log.debug(f'{uri}: Already in hgraph')

                try:
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
                            o=Literal(utcDatetimeIso(), datatype=XSD.dateTime)
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
