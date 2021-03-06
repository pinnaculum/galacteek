from galacteek.services import GService

from galacteek.ipfs.pubsub.srvs.chat import PSChatService


class ChatService(GService):
    name = 'chat'

    async def declareIpfsComponents(self):
        await self.ipfsPubsubService(
            PSChatService(self.app.ipfsCtx,
                          parent=self,
                          scheduler=self.app.scheduler,
                          config=self.serviceConfig))


def serviceCreate(dotPath, config, parent: GService):
    return ChatService(dotPath=dotPath, config=config)
