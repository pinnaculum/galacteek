import attr
from yarl import URL
from galacteek import AsyncSignal
from galacteek.config import cModuleContext
from galacteek.config import dictconfig


@attr.s(auto_attribs=True)
class EthereumConnectionParams:
    provType: str
    mode: str = 'auto'
    network: str = 'mainnet'

    infura: dictconfig.DictConfig = None

    @property
    def rpcUrl(self):
        if self.mode == 'infura' and self.infura:
            return str(URL(
                f'https://{self.network}.infura.io'
            ).with_path('/v3/' + self.infura['projectId']))

    @property
    def rpcUrlBeacon(self):
        if self.infura:
            return str(URL(
                'https://eth2-beacon-mainnet.infura.io'
            ).with_user(self.infura['projectId']).with_password(
                self.infura['apiKeySecret']
            ))


def ethConnConfigParams(network='mainnet'):
    try:
        with cModuleContext('galacteek.services.dweb.ethereum') as cfg:
            provType = cfg['providerType']
            mode = cfg.get('mode', 'infura')

            return EthereumConnectionParams(
                provType=provType,
                infura=cfg.get('infura', {}),
                mode=mode
            )
    except Exception:
        return EthereumConnectionParams(rpcUrl='http://localhost:7545',
                                        provType='http')


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
