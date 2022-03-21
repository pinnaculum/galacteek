from galacteek import log

from galacteek.services import GService

from galacteek.ld.iri import ipfsPeerUrn
from galacteek.ld.rdf.sync.base import BaseGraphSynchronizer
from galacteek.ld.rdf.sync.cfg import GraphSparQLSyncConfig
from galacteek.ld.sparql.aioclient import Sparkie


class GraphSparQLSynchronizer(BaseGraphSynchronizer):
    def __init__(self, config=None):
        self.config = config if config else GraphSparQLSyncConfig()

    async def sync(self, ipfsop, peerId, iri, dial,
                   auth):
        rdfService = GService.byDotName.get('ld.pronto')
        localGraph = rdfService.graphByUri(iri)

        if localGraph is None:
            return

        client = Sparkie(dial.httpUrl('/sparql'), auth=auth)

        peerUriRef = ipfsPeerUrn(peerId)

        for step in self.config.run:
            try:
                ctype = step.get('contentType', None)
                action = step.get('action', None)
                source = step.get('sourceGraph', 'remote')

                assert isinstance(step.query, str)

                q = step.query.replace(
                    '@REMOTE_PEERID@',
                    peerId
                ).replace(
                    '@REMOTE_PEER_URIREF@',
                    str(peerUriRef)
                )

                if not ctype:
                    if source == 'local':
                        await localGraph.queryAsync(q)
                    else:
                        await client.query(q)

                elif ctype == 'text/turtle':
                    g = await client.queryConstructGraph(q)

                    if g is None:
                        raise ValueError(
                            'Returned graph is invalid'
                        )

                    print(g.serialize(format='ttl'))

                    if action == 'merge':
                        await localGraph.guardian.mergeReplace(
                            g, localGraph)
            except Exception as err:
                log.debug(f'Sparql sync: step failed with error: {err}')

        await client.close()
