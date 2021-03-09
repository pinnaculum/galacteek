from galacteek import log
from galacteek import cached_property
from galacteek.services import GService

from galacteek.ipfs import ipfsOp
from galacteek.ipfs.pubsub.srvs.dagexchange import PSDAGExchangeService
from galacteek.ipfs.p2pservices import dagexchange


class DAGExchangeService(GService):
    name = 'dagexchange'

    @cached_property
    def dagExchService(self):
        return dagexchange.DAGExchangeService()

    async def declareIpfsComponents(self):
        await self.ipfsP2PService(self.dagExchService)

        await self.ipfsPubsubService(
            PSDAGExchangeService(self.app.ipfsCtx,
                                 parent=self,
                                 scheduler=self.app.scheduler)
        )

    @ipfsOp
    async def event_g_services_app(self, ipfsop, key, message):
        curProfile = ipfsop.ctx.currentProfile
        event = message['event']

        if event['type'] == 'IpfsRepositoryReady':
            # Allow these EDAGs to be signed

            log.debug('Allowing signing of the seeds EDAGs')

            self.dagExchService.allowEDag(
                curProfile.dagSeedsMain)
            self.dagExchService.allowEDag(
                curProfile.dagSeedsAll)


def serviceCreate(dotPath, config, parent: GService):
    return DAGExchangeService(dotPath=dotPath, config=config)
