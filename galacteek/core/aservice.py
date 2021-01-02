import asyncio
from pathlib import Path
from mode import Service
from mode.utils.objects import cached_property  # noqa

from galacteek import log
from galacteek.core import runningApp
from galacteek.core.ps import gHub
from galacteek.core.ps import makeKeyService
from galacteek.core.ps import keyServices


class GService(Service):
    name: str = 'gservice'
    ident: str = None

    def __init__(self, dataPath: Path = None, runtimeConfig=None):
        super().__init__()

        self.app = runningApp()
        self.rtCfg = runtimeConfig

        if dataPath:
            self.rootPath = dataPath
        else:
            self.rootPath = self.app.dataPathForService('tmp')

        self.psKey = makeKeyService(self.name)
        self.psKey = keyServices

    async def psPublish(self, event):
        gHub.publish(self.psKey, {
            'serviceIdent': self.ident,
            'event': event
        })
        await asyncio.sleep(0)

    async def on_start(self) -> None:
        log.debug(f'Creating service directory: {self.rootPath}')
        self.rootPath.mkdir(parents=True, exist_ok=True)
