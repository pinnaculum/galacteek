from galacteek.ipfs import ipfsOp
from galacteek.ipfs import ipfsOpFn

from galacteek.config.cmods import pinning as cfgpinning
from galacteek.core.ps import KeyListener
from galacteek.core.ps import makeKeyService


class RemotePinServicesManager(KeyListener):
    async def event_g_services_app(self, key, message):
        event = message['event']

        if event['type'] == 'IpfsOperatorChange':
            # IPFS connection change. Scan remote pin services
            await self.remoteServicesScan()

    @ipfsOp
    async def remoteServicesScan(self, ipfsop):
        """
        Scan remote pinning services and sync them to the config
        """

        nodeId = await ipfsop.nodeId()

        listing = await ipfsop.pinRemoteServiceList()

        if not nodeId or not listing:
            return

        for rService in listing:
            cfgpinning.rpsConfigRegister(rService, nodeId)


__all__ = ['RemotePinServicesManager']
