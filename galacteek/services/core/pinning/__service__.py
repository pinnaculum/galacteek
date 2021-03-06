import asyncio
from galacteek.services import GService

from galacteek.ipfs.pinning import remote


class RemotePinServicesMaster(GService):
    name = 'remotepinning'

    async def declareSystem(self):
        self.manager = remote.RemotePinServicesManager()

    @GService.task
    async def remoteObserver(self):
        while not self.should_stop:
            await self.manager.remoteServicesStat()
            await asyncio.sleep(5)



def serviceCreate(dotPath, config, parent: GService):
    return RemotePinServicesMaster(dotPath=dotPath, config=config)
