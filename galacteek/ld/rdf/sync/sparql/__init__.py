from galacteek.ipfs import ipfsOp
from galacteek.services import GService

from ..cfg import GraphSparQLSyncConfig


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
