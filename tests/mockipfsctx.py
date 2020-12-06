from galacteek import log
from galacteek.ipfs import ipfsOp

from galacteek.core.ctx import IPFSContext


class MockIPFSContext(IPFSContext):
    @ipfsOp
    async def setup(self, ipfsop, pubsubEnable=True,
                    pubsubHashmarksExch=False, p2pEnable=True,
                    offline=False):
        await self.importSoftIdent()
        await self.node.init()
        await self.peers.init()

        if p2pEnable is True and not offline:
            await self.p2p.init()

        await self.setupPubsub(pubsubHashmarksExch=pubsubHashmarksExch)

    async def start(self):
        log.debug('Starting IPFS context services')

        await self.pubsub.startServices()
        await self.p2p.startServices()

    async def shutdown(self):
        await self.peers.stop()
        await self.p2p.stop()
        await self.pubsub.stop()

    async def setupPubsub(self, pubsubHashmarksExch=False):
        pass
