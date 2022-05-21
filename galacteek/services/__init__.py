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
from galacteek.core.ps import KeyListener
from galacteek.core.ps import hubPublish
from galacteek.core.ps import makeKeyService

from galacteek.core.pkglister import pkgListPackages

from galacteek.config import configModRegCallback
from galacteek.config import configForModule
from galacteek.config import regConfigFromPyPkg

from galacteek.ld import ipsContextUri

servicesRootPath = Path(os.path.dirname(__file__))


class DisabledServiceException(Exception):
    pass


class DisabledServiceRecursiveException(Exception):
    pass


class GService(Service, KeyListener):
    name: str = 'gservice'
    ident: str = None
    configModuleName: str = None
    byDotName: dict = {}

    disabled: bool = False

    def __init__(self, dataPath: Path = None, runtimeConfig=None,
                 dotPath=None,
                 app=None,
                 config=None,
                 parent=None):
        self.app = app if app else runningApp()
        self.rtCfg = runtimeConfig
        self.dotPath = dotPath
        self.qtApi = None
        self._config = config

        self.sServiceStarted = AsyncSignal()

        if self.dotPath is None and parent and parent.dotPath:
            self.dotPath = f'{parent.dotPath}.{self.name}'

        if dataPath:
            self.rootPath = dataPath
        else:
            self.rootPath = self.app.dataPathForService(
                self.dotPath if self.dotPath else 'tmp')

        Service.__init__(self)
        KeyListener.__init__(self)

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

    async def psPublish(self, event, key=None):
        """
        Publish a service event message on the pubsub hub, to the
        service's PS key

        TODO: Use JSON-LD for all service messages
        """

        hubPublish(key if key else self.psKey, {
            'serviceIdent': self.ident,
            'event': event
        })

        await asyncio.sleep(0.05)

    async def ldPublish(self, event,
                        contextName='services/GenericServiceMessage',
                        key=None):
        """
        Publish a JSON-LD service event message on the
        pubsub hub, to the service's PS key
        """

        hubPublish(key if key else self.psKey, {
            '@context': str(ipsContextUri(contextName)),
            'serviceIdent': self.ident,
            'event': event
        })

        await asyncio.sleep(0.05)

    async def declareIpfsComponents(self):
        pass

    async def declareSystem(self):
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
        await self.declareSystem()

        if self.serviceConfigForIdent and 0:
            # Enable this when we want to have PS listen keys
            # definitions in the config
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

            srvMod = importlib.import_module(modName)

            if hasattr(srvMod, 'disabled'):
                disabled = getattr(srvMod, 'disabled')
                if disabled is True:
                    raise DisabledServiceException(
                          'Disabled service: {srvDotPath}')

            service = srvMod.serviceCreate(
                srvDotPath, config, parent)

            if not service or service.disabled is True:
                raise DisabledServiceException(
                      'Disabled service: {srvDotPath}')

            GService.byDotName[srvDotPath] = service
        except DisabledServiceException:
            log.debug(f'registerService ({srvDotPath}): service is disabled')
        except Exception:
            pass
        else:
            if add:
                await self.add_runtime_dependency(service)

            log.debug(f'registerService ({srvDotPath}): OK')

        s = parent if parent else self

        for pkgName, fullName in pkgListPackages(rootName):
            csDotPath = f'{srvDotPath}.{pkgName}'

            await s.registerService(csDotPath,
                                    parent=service,
                                    add=add)

        return service


def getByDotName(name):
    return GService.byDotName.get(name, None)
