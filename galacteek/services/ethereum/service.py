
from galacteek import log
from galacteek import cached_property
from galacteek.config import cParentGet
from galacteek.core.aservice import GService

from galacteek.blockchain.ethereum import MockEthereumController
from galacteek.blockchain.ethereum import ethConnConfigParams

from galacteek.services.ethereum import PS_EVENT_CONTRACTLOADED


class EthereumService(GService):
    ident = 'ethereum'

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

    @cached_property
    def ctrl(self):
        try:
            from galacteek.blockchain.ethereum.ctrl import EthereumController
            return EthereumController(ethConnConfigParams(
                self.app.cmdArgs.ethnet),
                parent=self.app,
                executor=self.app.executor)
        except ImportError:
            # Don't have the web3 package
            return MockEthereumController()

    async def on_start(self) -> None:
        await super().on_start()

        # if not cParentGet('enabled'):
        #     return

        log.debug('Starting ethereum service')
        await self.initEthereum()

    async def initEthereum(self):
        try:
            await self.ctrl.start()
        except Exception as err:
            log.debug(str(err))

    async def on_stop(self) -> None:
        log.debug('Stopping eth service')
