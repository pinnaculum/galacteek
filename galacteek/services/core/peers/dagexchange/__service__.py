from galacteek.services import GService

from galacteek.ipfs.pubsub.srvs.dagexchange import PSDAGExchangeService
from galacteek.ipfs.p2pservices import dagexchange


class DAGExchangeService(GService):
    name = 'dagexchange'

    async def declareIpfsComponents(self):
        await self.ipfsP2PService(dagexchange.DAGExchangeService())
        await self.ipfsPubsubService(
            PSDAGExchangeService(self.app.ipfsCtx,
                                 parent=self,
                                 scheduler=self.app.scheduler)
        )


def serviceCreate(dotPath, config, parent: GService):
    return DAGExchangeService(dotPath=dotPath, config=config)
