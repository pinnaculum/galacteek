import attr
from pathlib import Path

from galacteek.config import cParentGet
from galacteek.core.aservice import GService
from galacteek.core.aservice import cached_property
from galacteek.services.tor.process import TorLauncher


@attr.s(auto_attribs=True)
class TorServiceRuntimeConfig:
    cfgLocation: Path
    dataLocation: Path


class TorService(GService):
    @cached_property
    def proc(self):
        return TorLauncher(
            str(self.rtCfg.cfgLocation),
            str(self.rtCfg.dataLocation)
        )

    async def on_start(self):
        if cParentGet('enabled') is True:
            await self.proc.start()

    async def on_stop(self):
        await self.proc.stop()
