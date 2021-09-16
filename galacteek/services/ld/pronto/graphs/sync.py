import zlib
import attr
import aiohttp

from rdflib import RDF
from rdflib import URIRef

from galacteek import log
from galacteek.services import GService

from galacteek.ipfs import ipfsOp
from galacteek.ipfs.cidhelpers import IPFSPath

from galacteek.core import runningApp
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
    type: str = 'semchain'


class SmartQLClient:
    def __init__(self, dialCtx, auth: aiohttp.BasicAuth = None):
        self.dial = dialCtx

        self.auth = auth if auth else aiohttp.BasicAuth('smartql', 'default')
        self.spql = Sparkie(self.dial.httpUrl('/sparql'), auth=self.auth)

    async def resource(self, iri, context=None):
        rdfService = GService.byDotName.get('ld.pronto.graphs')
        graph = rdfService.graphByUri(iri)

        if graph is None:
            return

        url = self.dial.httpUrl(f'/resource/{iri}/graph')

        headers = {
            'Accept': 'application/x-turtle'
        }

        params = {
            'fmt': 'ttl',
            'context': context
        }

        try:
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
    async def syncFromRemote(self, ipfsop, iri: str, p2pEndpoint: str,
                             graphDescr=None):
        async with ipfsop.p2pDialerFromAddr(p2pEndpoint) as dial:
            if dial.failed:
                return False

            return await self.syncFromExport(ipfsop, iri, dial)

    async def syncFromExport(self, ipfsop, iri, dial):
        rdfService = GService.byDotName.get('ld.pronto.graphs')
        graph = rdfService.graphByUri(iri)

        if graph is None:
            return

        url = dial.httpUrl('/export')
        params = {
            'fmt': self.config.format,
            'compression': self.config.compression
        }

        try:
            async with aiohttp.ClientSession() as session:
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
    async def syncFromRemote(self, ipfsop, iri: str, p2pEndpoint: str,
                             graphDescr=None):
        async with ipfsop.p2pDialerFromAddr(p2pEndpoint) as dial:
            if dial.failed:
                return False

            return await self.syncFromExport(ipfsop, iri, dial)

    async def syncFromExport(self, ipfsop, iri, dial):
        rdfService = GService.byDotName.get('ld.pronto.graphs')
        graph = rdfService.graphByUri(iri)

        if graph is None:
            return


class GraphSemChainSynchronizer:
    def __init__(self, config=None):
        super().__init__()
        self.config = config if config else GraphSemChainSyncConfig()

    @ipfsOp
    async def syncFromRemote(self, ipfsop, iri: str, p2pEndpoint: str,
                             graphDescr=None):
        async with ipfsop.p2pDialerFromAddr(p2pEndpoint) as dial:
            if dial.failed:
                return False

            return await self._sync(ipfsop, iri, dial,
                                    graphDescr=graphDescr)

    def ontoloChainsList(self, hGraph):
        return list(hGraph.subjects(
            predicate=RDF.type,
            object=str(tUriOntoloChain)
        ))

    async def _sync(self, ipfsop, iri, dial, graphDescr=None):
        curProfile = ipfsop.ctx.currentProfile
        ipid = await curProfile.userInfo.ipIdentifier()
        rdfService = GService.byDotName.get('ld.pronto.graphs')
        graph = rdfService.graphByUri(iri)
        hGraph = rdfService.graphHistory

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
            log.debug(f'OntoloSync: {iri}: synchronizing chain {curi}')
            tsubj = f'urn:ontolochain:status:{curi}'

            await self.syncChain(
                hGraph,
                smartql,
                curi,
                tsubj
            )

        await smartql.spql.close()

    async def syncChain(self, hGraph,
                        smartql,
                        chainUri: URIRef,
                        trackerUri):
        tracker = hGraph.resource(trackerUri)

        if not tracker:
            return

        predCurObj = tUriSemObjCurrent

        for cn in range(0, 16):
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

            log.debug(f'syncOntoloChain ({chainUri}): current is {oIri}')

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
                        context=str(tUriOntoloChainRecord)
                    )

                    if await self.processObject(uri, gttl):
                        # Eat
                        hGraph.parse(data=gttl, format='ttl')
                    else:
                        log.debug(f'{uri}: failed to process ?!')
                else:
                    log.debug(f'{uri}: Already in hgraph')

                try:
                    async with hGraph.lock:
                        tracker.remove(
                            p=predCurObj
                        )
                        tracker.add(
                            p=predCurObj,
                            o=uri
                        )
                except Exception as err:
                    log.debug(
                        f'{chainUri}: update to {uri} error: {err}')
                else:
                    log.debug(
                        f'{chainUri}: advanced to {uri}')

            if objCount == 0:
                log.debug(f'{chainUri}: synced')
                break

    async def processObject(self, uri: URIRef, oTtl: str):
        app = runningApp()
        try:
            log.debug(f'Processing {uri}')
            g = BaseGraph().parse(data=oTtl)

            o = g.resource(uri)
            path = o.value(p=tUriIpfsPath)

            await app.s.rdfStore(IPFSPath(path))
        except Exception as err:
            log.debug(f'process {uri}: ERROR: {err}')
        else:
            log.debug(f'process {uri}: SUCCESS')
            return True
