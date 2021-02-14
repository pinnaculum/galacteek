import io
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
        self._app = kw.pop('app')

        super().__init__(*args, **kw)

    @cached_property
    def bmService(self) -> BitMessageClientService:
        return BitMessageClientService(
            self._app._bitMessageDataLocation
        )

    @cached_property
    def ethService(self) -> EthereumService:
        return EthereumService(
            self._app._ethDataLocation
        )

    @cached_property
    def torService(self) -> TorService:
        return TorService(
            self._app.dataPathForService('tor'),
            TorServiceRuntimeConfig(
                cfgLocation=self._app._torConfigLocation,
                dataLocation=self._app._torDataDirLocation
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
            assert self._app.cmdArgs.memprofiling is True
        except (ImportError, Exception):
            pass

        while not self.should_stop:
            await asyncio.sleep(10)

            lt = int(self._app.loop.time())

            usage = memory_usage(-1, interval=.2, timeout=1)
            if usage:
                log.debug(
                    f'Memory Usage (LT: {lt}): {usage[0]}'
                )

    async def getGraphImage(self) -> None:
        try:
            import pydot
        except ImportError:
            return

        try:
            out = io.StringIO()
            beacon = self.beacon.root or self.beacon
            beacon.as_graph().to_dot(out)
            graph, = pydot.graph_from_dot_data(out.getvalue())
        except Exception:
            return

        with open('ggraph.png', 'wb') as fh:
            fh.write(graph.create_png())
