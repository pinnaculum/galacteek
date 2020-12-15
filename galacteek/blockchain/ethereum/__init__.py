from galacteek import AsyncSignal
from galacteek.config import cModuleContext


class EthereumConnectionParams:
    def __init__(self, rpcUrl, provType='http'):
        self.provType = provType
        self.rpcUrl = rpcUrl


def ethConnConfigParams(network='mainnet'):
    with cModuleContext('galacteek.blockchain.ethereum') as cfg:
        provType = cfg['conn']['networks'][network]['providerType']
        rpcUrl = cfg['conn']['networks'][network]['rpcUrl']
        return EthereumConnectionParams(rpcUrl, provType=provType)


class MockEthereumController:
    ethConnected = AsyncSignal(bool)
    ethNewBlock = AsyncSignal(str)

    def changeParams(self, params):
        self._params = params

    def getWeb3(self):
        return None

    async def stop(self):
        pass

    async def start(self):
        pass

    async def latestBlock(self):
        pass

    async def getBlock(self, block='latest'):
        pass

    async def connected(self):
        return False
