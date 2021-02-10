import importlib
import os.path
import os
import jinja2

from PyQt5.QtCore import QTimer  # noqa

from galacteek import log
from galacteek.core.objects import pyqtSignal
from galacteek.core import runningApp
from galacteek.core import pkgResourcesListDir
from galacteek.core import pkgResourcesRscFilename
from galacteek.services import GService
from galacteek.config import cGet
from galacteek.dweb import render
from galacteek.ipfs import ipfsOp
from galacteek.core.fswatcher import FileWatcher

from galacteek.browser.web3channels import Web3Channel

from galacteek.services.ethereum import PS_EVENT_CONTRACTLOADED

dappsPkg = __name__


def availableDapps():
    try:
        listing = pkgResourcesListDir(dappsPkg, '')
        for fn in listing:
            path = pkgResourcesRscFilename(dappsPkg, fn)
            if not fn.startswith('_') and os.path.isdir(path):
                yield fn, path
    except Exception as err:
        log.debug(str(err))


def dappGetModule(dappName):
    modname = f'{dappsPkg}.{dappName}'

    try:
        module = importlib.import_module(modname)
    except Exception as err:
        log.debug(f'Error importing dapp module: {modname}: {err}')
    else:
        return module


def dappsRegisterSchemes():
    # Called early (register dapps schemes before app creation)

    for dappName, dappPath in availableDapps():
        mod = dappGetModule(dappName)
        if mod:
            log.debug(f'Registering ipdapp schemes for {dappName}')
            mod.declareUrlSchemes()
        else:
            log.info(f'Cannot load dapp {dappName}')


class IPDapp(GService):
    """
    Inter-Planetary Dapp
    """

    pkgContentsChanged = pyqtSignal(str)

    schemeHandler: object = None
    web3Channel: Web3Channel = None

    name = 'ipdapp'

    # service identifier
    ident = 'ipdapp'

    def __init__(self, ethCtrl, name, pkgPath,
                 offline=False, **kwargs):
        planet = kwargs.pop('planet', 'earth')
        initmod = kwargs.pop('initModule', None)

        super(IPDapp, self).__init__()

        self.app = runningApp()

        self._ethController = ethCtrl
        self._name = name
        self._pkgPath = pkgPath
        self._templatesPath = os.path.join(self._pkgPath, 'templates')
        self._assetsPath = os.path.join(self._pkgPath, 'assets')
        self._assetsCid = None
        self._args = kwargs
        self._planet = planet
        self._offline = offline
        self.cStore = {}

        self._ctx_params = {}

        self.jEnv = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self._templatesPath),
            enable_async=True
        )

        self.web3Channel = self.app.browserRuntime.web3Channel(
            self.name)

        self._moduleInit = initmod
        self._watcher = FileWatcher()
        # self._watchT = QTimer()
        # self._watchT.timeout.connect(
        #    lambda: self.pkgContentsChanged.emit(self.name))

        self.watch(self._pkgPath)
        self._watcher.pathChanged.connect(self.onFileWatchChange)

    @property
    def offline(self):
        # DAGs and assets in 'offline' mode (dev)
        return self._offline

    @property
    def planet(self):
        return self._planet

    @property
    def ethCtrl(self):
        return self._ethController

    @property
    def args(self):
        return self._args

    @property
    def assetsCid(self):
        return self._assetsCid

    async def registerSchemeHandlers(self):
        pass

    def watch(self, _dir):
        for root, dirs, files in os.walk(_dir):
            for d in dirs:
                if d.startswith('__'):
                    continue
                fp = os.path.join(root, d)
                self._watcher.watch(fp)
        self._watcher.watch(_dir)

    def compileTemplates(self):
        try:
            self.jEnv.compile_templates(self._templatesPath, zip=None)
        except Exception as err:
            log.debug(f'Templates recompile error: {err}')

    @ipfsOp
    async def dappInit(self, ipfsop):
        self.compileTemplates()
        await self.loadContracts()
        await self.importAssets()

    def stop(self):
        pass

    @ipfsOp
    async def importAssets(self, ipfsop):
        if os.path.isdir(self._assetsPath):
            self._assetsCid = await ipfsop.addPath(
                self._assetsPath, recursive=True,
                offline=self.offline
            )

    async def renderTemplate(self, template, **kw):
        coro = render.ipfsRender
        kw.update(self._ctx_params)
        kw['offline'] = self.offline

        return await coro(self.jEnv,
                          template,
                          **kw
                          )

    async def renderTemplateWLink(self, dag, tmpl, **kw):
        # Render and link in the dag
        result = await self.renderTemplate(tmpl, **kw)
        return dag.mkLink(result)

    def onFileWatchChange(self, path):
        # self._watchT.stop()
        # self._watchT.start(3000)
        pass

    def reimportModule(self):
        self._watchT.stop()
        if self._moduleInit:
            try:
                importlib.reload(self._moduleInit)
            except ImportError:
                log.debug('Error reimporting module {}'.format(
                    self._moduleInit))

    async def dappReload(self):
        log.debug('Dapp reload')
        self._watchT.stop()

        await self.importAssets()
        self.compileTemplates()

    async def loadContracts(self):
        config = cGet('contracts.deployed',
                      'galacteek.ipdapps.{self.name}')
        await self.loadContractsFromConfig(config)

    async def loadContractsFromConfig(self, config):
        dpls = config

        if not dpls:
            return

        for cConfig in dpls:
            try:
                ident = cConfig.get('ident')
                name = cConfig.get('name')
                addr = cConfig.get('address')

                if not ident or ident in self.cStore:
                    continue

                lContract, lOp = await self.ethCtrl.loadLocalContractFromAddr(
                    name, addr)

                if lOp:
                    self.cStore[ident] = lOp

                    await self.psPublish({
                        'type': PS_EVENT_CONTRACTLOADED,
                        'contractConfig': cConfig,
                        'contract': {
                            'address': addr,
                            'name': name,
                            'operator': lOp,
                            'webchannel': cConfig.get('web3Channel'),
                            'web3Channel': cConfig.get('web3Channel')
                        }
                    })

                    # It's a service
                    await lOp.start()
            except Exception as err:
                import traceback
                traceback.print_exc()
                log.debug(str(err))
