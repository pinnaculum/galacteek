import asyncio
import shutil

from pathlib import Path
from mode import Service
from mode.utils.objects import cached_property  # noqa

from galacteek import log
from galacteek.core import runningApp
from galacteek.core.ps import hubPublish
from galacteek.core.ps import makeKeyService
from galacteek.config import configModRegCallback
from galacteek.config import configForModule


class GService(Service):
    name: str = 'gservice'
    ident: str = None
    configModuleName: str = None

    def __init__(self, dataPath: Path = None, runtimeConfig=None):
        super().__init__()

        self.app = runningApp()
        self.rtCfg = runtimeConfig

        if dataPath:
            self.rootPath = dataPath
        else:
            self.rootPath = self.app.dataPathForService('tmp')

        self.psKey = makeKeyService(self.name)

        self.serviceConfigBind()

    @property
    def serviceConfig(self):
        return configForModule(self.configModuleName)

    def serviceConfigBind(self, mod=None):
        configModRegCallback(self.onConfigChangedAsync,
                             mod=self.configModuleName)

    async def onConfigChangedAsync(self):
        pass

    def which(self, prog):
        return shutil.which(prog)

    async def psPublish(self, event):
        """
        Publish a service event message on the pubsub hub, to the
        service's PS key

        TODO: Use JSON-LD for all service messages
        """

        hubPublish(self.psKey, {
            'serviceIdent': self.ident,
            'event': event
        })

        await asyncio.sleep(0.01)

    async def on_start(self) -> None:
        log.debug(f'Creating service directory: {self.rootPath}')

        self.rootPath.mkdir(parents=True, exist_ok=True)
