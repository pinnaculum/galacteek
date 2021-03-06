from galacteek.services import GService

from galacteek.ipfs.p2pservices import didauth


class DIDAuthService(GService):
    name = 'didauth'

    async def declareIpfsComponents(self):
        # self.didAuthService = didauth.DIDAuthService()

        await self.ipfsP2PService(didauth.DIDAuthService())


def serviceCreate(dotPath, config, parent: GService):
    return DIDAuthService(dotPath=dotPath, config=config)
