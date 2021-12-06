from rdflib import URIRef
from rdflib.resource import Resource

from galacteek.ipfs import ipfsOpFn
from galacteek.core import utcDatetimeIso
from galacteek.ld import gLdDefaultContext
from galacteek.ld.sparql import select, where, T
from galacteek import log


class OntoloChain(Resource):
    def qgenAllGeoEmitters(self):
        return select(
            vars=['?uri'],
            w=where([
                T(subject='?uri', predicate="a",
                  object="gs:OntoloChainGeoEmitter"),
                T(subject='?uri', predicate="gs:ontoloChain",
                  object=f'<{self.identifier}>')
            ])
        )

    def qgenAllGeoTransponders(self):
        return select(
            vars=['?uri'],
            w=where([
                T(subject='?uri', predicate="a",
                  object="gs:OntoloChainGeoTransponder"),
                T(subject='?uri', predicate="gs:ontoloChain",
                  object=f'<{self.identifier}>')
            ])
        )

    def qgenVCRecords(self):
        return select(
            vars=['?uri'],
            w=where([
                T(subject='?uri', predicate="a",
                  object="gs:OntoloChainVCRecord"),
                T(subject='?uri', predicate="gs:ontoloChain",
                  object=f'<{self.identifier}>')
            ])
        )


def getChainResource(graph, uri):
    return OntoloChain(graph, uri)


def subDidChainUri(ipid, name: str):
    return URIRef(f'urn:ontolochain:ipid:{ipid.id}:{name}')


def didMainChainUri(ipid):
    return URIRef(f'urn:ontolochain:ipid:{ipid.id}')


async def selectByUri(graph, chainUri):
    async with graph.lock:
        return list(await graph.queryAsync(
            '''
                PREFIX gs: <ips://galacteek.ld/>
                SELECT ?chainUri
                WHERE {
                    ?chainUri a gs:OntoloChain .
                }
                ''',
            initBindings={
                'chainUri': chainUri
            }
        ))


@ipfsOpFn
async def create(ipfsop,
                 graph, ipid, chainId, peerId,
                 description=''):
    ex = await selectByUri(graph, chainId)
    if len(ex) > 0:
        return False

    async with graph.lock:
        log.debug(f'Creating ontolochain: {chainId}')

        doc = await ipid.jsonLdSign({
            '@context': gLdDefaultContext,
            '@type': 'OntoloChain',
            '@id': chainId,
            'peerId': peerId,
            'description': description,
            'dateCreated': utcDatetimeIso()
        })

        await graph.pullObject(doc)
