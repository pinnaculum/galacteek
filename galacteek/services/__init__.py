import asyncio
import shutil
import os.path
import importlib
from pathlib import Path

from mode import Service
from mode.utils.objects import cached_property  # noqa

from galacteek import log
from galacteek import AsyncSignal

from galacteek.core import runningApp
from galacteek.core import pkgResourcesDirEntries
from galacteek.core import pkgResourcesRscFilename
from galacteek.core.ps import KeyListener
from galacteek.core.ps import hubPublish
from galacteek.core.ps import makeKeyService

from galacteek.config import configModRegCallback
from galacteek.config import configForModule
from galacteek.config import regConfigFromPyPkg

from galacteek.ld import ipsContextUri


servicesRootPath = Path(os.path.dirname(__file__))


class GService(Service, KeyListener):
    name: str = 'gservice'
    ident: str = None

    # dotPath: str = None

    configModuleName: str = None

    pubsubServices: list = []

    byDotName: dict = {}

    def __init__(self, dataPath: Path = None, runtimeConfig=None,
                 dotPath=None,
                 app=None,
                 config=None,
                 parent=None):
        super(GService, self).__init__()

        self.app = app if app else runningApp()
        self.rtCfg = runtimeConfig
        self.dotPath = dotPath
        self._config = config

        self.sServiceStarted = AsyncSignal()

        if self.dotPath is None and parent and parent.dotPath:
            self.dotPath = f'{parent.dotPath}.{self.name}'

        if dataPath:
            self.rootPath = dataPath
        else:
            self.rootPath = self.app.dataPathForService(
                self.dotPath if self.dotPath else 'tmp')

        self.pubsubServices = []

        self.serviceConfigBind()

    @cached_property
    def psKey(self):
        return makeKeyService(*(self.dotPath.split('.')))

    @property
    def serviceConfig(self):
        return self._config if self._config else configForModule(
            self.configModuleName)

    @property
    def serviceConfigForIdent(self):
        try:
            return self.serviceConfig.services.get(self.dotPath)
        except Exception:
            return

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

    async def ldPublish(self, event,
                        contextName='services/GenericServiceMessage'):
        """
        Publish a service event message on the pubsub hub, to the
        service's PS key

        TODO: Use JSON-LD for all service messages
        """

        hubPublish(self.psKey, {
            '@context': ipsContextUri(contextName),
            'serviceIdent': self.ident,
            'event': event
        })

        await asyncio.sleep(0.01)

    async def declareIpfsComponents(self):
        pass

    async def ipfsPubsubService(self, service):
        # Register a pubsub service
        await self.add_runtime_dependency(service)

        self.app.ipfsCtx.pubsub.reg(service)

    async def ipfsP2PService(self, service):
        # Register a P2P service
        await self.add_runtime_dependency(service)
        await self.app.ipfsCtx.p2p.register(service)

    async def on_start(self) -> None:
        log.debug(f'Creating service directory: {self.rootPath}')

        self.rootPath.mkdir(parents=True, exist_ok=True)

        await self.declareIpfsComponents()

        if self.serviceConfigForIdent:

            self.psListenFromConfig(self.serviceConfigForIdent)

    async def walkServices(self, dot: str, add=False):
        await self.registerService(dot, add=add)

    async def registerService(self, srvDotPath: str, add=False,
                              parent=None,
                              parentDot=None):
        service = None

        if parentDot:
            rootName = f'{parentDot}.{srvDotPath}'
        else:
            rootName = f'galacteek.services.{srvDotPath}'

        modName = f'{rootName}.__service__'

        try:
            regConfigFromPyPkg(rootName)
            config = configForModule(rootName)
            # print(self.dotPath, config)

            mod = importlib.import_module(modName)
            service = mod.serviceCreate(
                srvDotPath, config, parent)

            GService.byDotName[srvDotPath] = service
        except Exception as err:
            log.debug(f'registerService ({srvDotPath}): Error {err}')
        else:
            if add:
                await self.add_runtime_dependency(service)

            log.debug(f'registerService ({srvDotPath}): OK')

        s = parent if parent else self
        for dotName in pkgResourcesDirEntries(rootName):
            csDotPath = f'{srvDotPath}.{dotName}'

            path = Path(pkgResourcesRscFilename(rootName, dotName))
            if path.is_dir():
                await s.registerService(csDotPath,
                                        parent=service,
                                        add=add)

        return service
