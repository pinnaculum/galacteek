from rdflib import URIRef

from galacteek.ipfs import ipfsOpFn
from galacteek.core import utcDatetimeIso
from galacteek.ld import gLdDefaultContext
from galacteek import log


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
