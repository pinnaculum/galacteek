from galacteek.services import GService

from galacteek.ipfs.pubsub.srvs.peers import PSPeersService


class IdentService(GService):
    name = 'ident'

    async def declareIpfsComponents(self):
        await self.ipfsPubsubService(
            PSPeersService(self.app.ipfsCtx,
                           parent=self,
                           scheduler=self.app.scheduler,
                           config=self.serviceConfig))


def serviceCreate(dotPath, config, parent: GService):
    return IdentService(dotPath=dotPath, config=config)
