import attr
from galacteek import AsyncSignal
from galacteek.config import cModuleContext
from galacteek.config import dictconfig


@attr.s(auto_attribs=True)
class EthereumConnectionParams:
    rpcUrl: str
    provType: str
    mode: str = 'auto'

    infura: dictconfig.DictConfig = None


def ethConnConfigParams(network='mainnet'):
    with cModuleContext('galacteek.services.ethereum') as cfg:
        provType = cfg['providerType']
        rpcUrl = cfg['rpcUrl']
        mode = cfg.get('mode', 'infura')

        return EthereumConnectionParams(rpcUrl=rpcUrl,
                                        provType=provType,
                                        infura=cfg['infura'],
                                        mode=mode)


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
