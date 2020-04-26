from galacteek import AsyncSignal


class EthereumConnectionParams:
    def __init__(self, rpcUrl, provType='http'):
        self.provType = provType
        self.rpcUrl = rpcUrl


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
