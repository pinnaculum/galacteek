import asyncio

from galacteek import log
from galacteek.services import GService
from galacteek.services import cached_property
from galacteek.services.net.bitmessage.service import BitMessageClientService
from galacteek.services.net.tor.service import TorService
from galacteek.services.net.tor.service import TorServiceRuntimeConfig
from galacteek.services.ethereum.service import EthereumService


class AppService(GService):
    """
    Main service
    """

    # Bitmessage service
    bmService: BitMessageClientService = None

    # Tor service
    torService: TorService = None

    # Eth
    ethService: EthereumService = None

    def __init__(self, *args, **kw):
        self.app = kw.pop('app')

        super().__init__(*args, **kw)

    @cached_property
    def bmService(self) -> BitMessageClientService:
        return BitMessageClientService(
            self.app._bitMessageDataLocation
        )

    @cached_property
    def ethService(self) -> EthereumService:
        return EthereumService(
            self.app._ethDataLocation
        )

    @cached_property
    def torService(self) -> TorService:
        return TorService(
            self.app.dataPathForService('tor'),
            TorServiceRuntimeConfig(
                cfgLocation=self.app._torConfigLocation,
                dataLocation=self.app._torDataDirLocation
            )
        )

    async def on_start(self) -> None:
        log.debug('Starting main application service')

        # Dependencies

        log.debug('Adding runtime dependencies')

        await self.add_runtime_dependency(self.bmService)
        await self.add_runtime_dependency(self.torService)
        await self.add_runtime_dependency(self.ethService)

    async def on_stop(self) -> None:
        log.debug('Stopping main application service')

    @GService.task
    async def mProfileTask(self):
        try:
            from memory_profiler import memory_usage
            assert self.app.cmdArgs.memprofiling is True
        except (ImportError, Exception):
            pass

        while not self.should_stop:
            await asyncio.sleep(10)

            lt = int(self.app.loop.time())

            usage = memory_usage(-1, interval=.2, timeout=1)
            if usage:
                log.debug(
                    f'Memory Usage (LT: {lt}): {usage[0]}'
                )
