import hashlib
import asyncio
import aiohttp

from rdflib import URIRef

from galacteek import log
from galacteek.services import GService

from galacteek.core import utcDatetimeIso
from galacteek.core import runningApp

from galacteek.ipfs.cidhelpers import IPFSPath

from galacteek.ipfs import ipfsOp
from galacteek.ipfs.pubsub.messages.ld import SparQLHeartbeatMessage

from galacteek.ld import gLdDefaultContext
from galacteek.ld import ontolochain
from galacteek.ld.sparql.aioclient import Sparkie
from galacteek.ld.signatures import jsonldsig


class GraphHistorySynchronizer:
    def __init__(self, hGraph):
        self.hGraph = hGraph

    @ipfsOp
    async def syncFromRemote(self, ipfsop, iri: str, p2pEndpoint: str):
        async with ipfsop.p2pDialerFromAddr(p2pEndpoint) as dial:
            if dial.failed:
                # Bummer
                return

            await self.syncFromExport(ipfsop, iri, dial)

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

    async def syncFromExport(self, ipfsop, iri, dial):
        rdfService = GService.byDotName.get('ld.pronto')
        graph = rdfService.graphByUri(iri)
        if graph is None:
            return

        url = dial.httpUrl('/export')

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    data = await resp.read()
                    assert data is not None

                    graph.parse(data=data.decode(), format='xml')
        except Exception as err:
            print(str(err))
        else:
            print(f'Graph with IRI {iri}: synced from export')

    async def syncSparql(self, ipfsop, dial):
        sparql = Sparkie(dial.httpUrl('/sparql'))

        ids = await self.storedObjectsIds()

        q = """
            PREFIX gs: <ips://galacteek.ld/>
            SELECT ?uri ?dateCreated ?ipfsPath
            WHERE {
                ?uri a gs:OntoloChainRecord ;
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
        return GService.byDotName.get('ld.pronto')

    @property
    def hGraph(self):
        return self.rdfService.graphByUri('urn:ipg:h0')

    @property
    def mainGraph(self):
        return self.rdfService.graphG

    def on_init(self):
        self.trail = None

    async def on_start(self):
        await super().on_start()
        self.synchro = GraphHistorySynchronizer(self.hGraph)

    async def ontoloChainCreate(self, ipid, chainId, peerId):
        from galacteek.ld.ontolochain import create

        return await create(self.hGraph, ipid, chainId, peerId)

    async def trustTokenForDid(self, did: str):
        tokens = list(await self.mainGraph.queryAsync(
            '''
            PREFIX gs: <ips://galacteek.ld/>
            PREFIX trustToken: <ips://galacteek.ld/OntoloTrustToken#>
            SELECT ?uri
            WHERE {
                ?uri a gs:OntoloTrustToken ;
                  trustToken:holder ?did .
            }
            LIMIT 1
            ''',
            initBindings={'did': did}
        ))
        if tokens:
            return tokens.pop(0)[0]

    @ipfsOp
    async def trace(self, ipfsop,
                    iPath: IPFSPath,
                    graphUri: str,
                    recordType='OntoloChainRecord',
                    chainUri: URIRef = None):
        """
        Main history API (trace an object in the history graph)
        """

        ipfsCtx = ipfsop.ctx
        profile = ipfsCtx.currentProfile
        ipid = await profile.userInfo.ipIdentifier()
        rsaAgent = await ipid.rsaAgentGet(ipfsop)
        privKey = await rsaAgent._privateKey()

        # Graph where we store the ontolorecord
        # dstGraph = self.rdfService.graphByUri(graphUri)
        dstGraph = self.rdfService.graphHistory

        if dstGraph is None:
            log.debug(f'trace: graph with URI {graphUri} was not found')
            return

        if not ipid:
            log.debug('No IPID found')
            return

        dagraw = await ipfsop.dagGet(str(iPath), timeout=15)
        if not dagraw:
            log.debug(f'trace: object {iPath} could not be retrieved')
            return

        h = hashlib.sha1()
        h.update(iPath.ipfsUrl.encode())

        if recordType == 'OntoloChainRecord':
            nodeId = f'urn:ontolorecord:{h.hexdigest()}'
        elif recordType == 'OntoloChainVCRecord':
            nodeId = f'urn:ontolovcrecord:{h.hexdigest()}'
        else:
            log.debug(f'Invalid record type {recordType}')
            return

        chainId = chainUri if chainUri else ontolochain.didMainChainUri(ipid)

        chains = await ontolochain.selectByUri(dstGraph, chainId)

        if len(chains) == 0:
            await self.ontoloChainCreate(
                ipid, chainId, ipfsCtx.node.id)

        lastObjs = list(await dstGraph.queryAsync(
            '''
            PREFIX gs: <ips://galacteek.ld/>
            SELECT ?uri ?date ?objNum
            WHERE {
                ?uri a gs:OntoloChainRecord ;
                  gs:dateCreated ?date ;
                  gs:objectNumber ?objNum ;
                  gs:ontoloChain ?chainUri .
            }
            ORDER BY DESC(?date)
            LIMIT 1
            ''',
            initBindings={'chainUri': chainId}
        ))

        if not lastObjs:
            objNumber = 0

            prevBlock = {
                '@type': 'OntoloChainRecord',
                '@id': 'urn:ontolorecord:0'
            }
        else:
            # Previous object link

            row = lastObjs.pop(0)
            objNumber = int(row['objNum']) + 1

            prevBlock = {
                '@type': 'OntoloChainRecord',
                '@id': str(row['uri'])
            }

        result = list(dstGraph.predicate_objects(nodeId))

        if result:
            return

        doc = {
            '@context': gLdDefaultContext,
            '@type': recordType,
            '@id': nodeId,

            'didCreator': {
                '@type': 'did',
                '@id': ipid.did
            },

            'ontoloChain': {
                '@type': 'OntoloChain',
                '@id': chainId
            },

            'objectNumber': objNumber,

            'ontoloBlockPrevious': prevBlock,

            'dateCreated': utcDatetimeIso(),
            'ipfsPath': str(iPath),
            'outputGraph': graphUri,

            'verificationMethod': f'{ipid.did}#keys-1',
            'signature': jsonldsig.signsa(dagraw, privKey.exportKey())
        }

        await dstGraph.pullObject(doc)

        trustToken = await self.trustTokenForDid(ipid.did)

        if trustToken:
            commitId = f'{nodeId}:commit'

            commit = await ipid.jsonLdSign({
                '@context': gLdDefaultContext,
                '@type': 'OntoloChainCommit',

                '@id': commitId,

                'ontoloBlock': {
                    '@type': 'OntoloChainRecord',
                    '@id': nodeId
                },

                'ontoloChain': {
                    '@type': 'OntoloChain',
                    '@id': chainId
                },

                'ontoloTrustToken': {
                    '@id': str(trustToken)
                },

                'dateCreated': utcDatetimeIso()
            })

            await dstGraph.pullObject(commit)

    # @GService.task
    async def watch(self):
        while not self.should_stop:
            await asyncio.sleep(30)

            msg = SparQLHeartbeatMessage.make()
            msg.graphs.append({
                'graphIri': self.hGraph.identifier,
                'smartqlEndpointAddr': self.sqlService.endpointAddr()
            })

            await self.rdfService.psService.send(msg)


def serviceCreate(dotPath, config, parent: GService):
    return GraphingHistoryService(dotPath=dotPath, config=config)
