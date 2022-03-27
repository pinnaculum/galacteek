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
                   auth, p2pLibrarianId=None):
        rdfService = GService.byDotName.get('ld.pronto')
        localGraph = rdfService.graphByUri(iri)

        if localGraph is None:
            return

        client = Sparkie(dial.httpUrl('/sparql'), auth=auth)

        peerUriRef = ipfsPeerUrn(peerId)

        for step in self.config.run:
            try:
                sname = step.get('name', 'unknown')
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

                if p2pLibrarianId:
                    q = q.replace(
                        '@REMOTE_P2P_LIBRARIANID@',
                        str(p2pLibrarianId)
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

                    if self.config.debug:
                        print(g.serialize(format='ttl'))

                    if action == 'merge':
                        await localGraph.guardian.mergeReplace(
                            g, localGraph)
                    else:
                        raise ValueError(f'Unknown step action: {action}')
            except Exception as err:
                log.debug(f'Sparql sync for graph {iri}: '
                          f'step {sname} failed with error: {err}')

        await client.close()
