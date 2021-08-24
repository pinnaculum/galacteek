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

                    print('resource data is', gdata)

                    graph.parse(data=gdata, format=params['fmt'])
        except Exception as err:
            print(str(err))
        else:
            print(f'Graph with IRI {iri}: retrieved')
            return gdata


class GraphExportSynchronizer:
    def __init__(self, config=None):
        self.config = config if config else GraphExportSyncConfig()

    @ipfsOp
    async def syncFromRemote(self, ipfsop, iri: str, p2pEndpoint: str):
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

                    print(gdata)
                    graph.parse(data=gdata, format=params['fmt'])
        except Exception as err:
            print(str(err))
        else:
            print(f'Graph with IRI {iri}: synced from export')


class GraphSparQLSynchronizer:
    def __init__(self, config=None):
        self.config = config if config else GraphSparQLSyncConfig()

    @ipfsOp
    async def syncFromRemote(self, ipfsop, iri: str, p2pEndpoint: str):
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
    async def syncFromRemote(self, ipfsop, iri: str, p2pEndpoint: str):
        async with ipfsop.p2pDialerFromAddr(p2pEndpoint) as dial:
            if dial.failed:
                return False

            return await self.syncFromExport(ipfsop, iri, dial)

    def ontoloChainsList(self, hGraph):
        return list(hGraph.subjects(
            predicate=RDF.type,
            object=str(tUriOntoloChain)
        ))

    async def syncFromExport(self, ipfsop, iri, dial):
        curProfile = ipfsop.ctx.currentProfile
        ipid = await curProfile.userInfo.ipIdentifier()
        rdfService = GService.byDotName.get('ld.pronto.graphs')
        graph = rdfService.graphByUri(iri)
        hGraph = rdfService.graphHistory

        if graph is None or not ipid:
            return

        smartql = SmartQLClient(
            dial, auth=aiohttp.BasicAuth('smartql', 'password')
        )

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
            print(str(err))
            pass

        for curi in chains:
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
        predCurObj = tUriSemObjCurrent

        w = where([
            T(subject='?uri', predicate="a", object="gs:OntoloChainRecord"),
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
            uri = URIRef(res['uri']['value'])

            # ex = hGraph.resource(str(uri))
            ex = hGraph.value(subject=uri, predicate=RDF.type)
            if not ex:
                # Fetch the object record
                gttl = await smartql.resource(
                    str(uri),
                    context=str(tUriOntoloChainRecord)
                )
                print(gttl)

                if await self.processObject(uri, gttl):
                    # Eat
                    hGraph.parse(data=gttl, format='ttl')
            else:
                log.debug(f'{uri}: Already in hgraph')

            try:
                tracker.remove(
                    p=predCurObj
                )
                tracker.add(
                    p=predCurObj,
                    o=uri
                )
            except Exception as err:
                print(err)

    async def processObject(self, uri: URIRef, oTtl: str):
        app = runningApp()
        try:
            log.debug(f'Processing {uri}')
            g = BaseGraph().parse(data=oTtl)

            o = g.resource(uri)
            path = o.value(p=tUriIpfsPath)

            await app.s.rdfStore(IPFSPath(path))
        except Exception as err:
            print(err)
        else:
            log.debug(f'{uri}: SUCCESS')
            return True
