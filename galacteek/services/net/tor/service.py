import attr
from pathlib import Path

from galacteek.config import cParentGet

from galacteek.services import GService
from galacteek.services import cached_property
from galacteek.services.net.tor.process import TorLauncher


@attr.s(auto_attribs=True)
class TorServiceRuntimeConfig:
    cfgLocation: Path
    dataLocation: Path


class TorService(GService):
    configModuleName = 'galacteek.services.net.tor'

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
        try:
            await self.proc.stop()
        except Exception:
            pass

    async def onConfigChangedAsync(self):
        if self.proc.running is True:
            if not self.serviceConfig.enabled:
                await self.stop()
        else:
            if self.serviceConfig.enabled:
                await self.restart()
