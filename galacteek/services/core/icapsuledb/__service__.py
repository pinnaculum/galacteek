from pathlib import Path
from omegaconf import OmegaConf
import attr
import asyncio
import aiohttp
import tarfile
import hashlib
from io import BytesIO
from yarl import URL

from galacteek import log
from galacteek.core.asynclib import asyncWriteFile
from galacteek.core.asynclib import asyncReadFile
from galacteek.services import GService
from galacteek.ipfs import ipfsOp
from galacteek.ipfs.cidhelpers import IPFSPath


@attr.s(auto_attribs=True)
class CapsuleContext:
    uri: str = ''
    type: str = ''
    qdef: dict = {}
    depends: list = []
    components: list = []
    qmlEntryPoint: str = ''


class ICapsuleRegistryLoaderService(GService):
    """
    Service that loads QML apps from IPFS and notifies
    the application when they're ready to be used.
    """

    name = 'qmlcomponents'

    def on_init(self):
        self.lock = asyncio.Lock()
        self.dappsStoragePath = self.rootPath.joinpath('components')
        self.dappsStoragePath.mkdir(exist_ok=True, parents=True)
        self._qc = {}
        self._byUri = {}
        self._dappLoadedByUri = {}
        self._processing = False

    def capsuleCtx(self, uri: str):
        return self._byUri.get(uri)

    async def on_start(self):
        pass

    async def event_g_services_app(self, key, message):
        event = message['event']

        # TODO: event repo ready or peer count > 0
        if event['type'] == 'IpfsRepositoryReady':
            await self.loadCapsulesFromSources()
        elif event['type'] == 'QmlApplicationLoaded':
            uri = event.get('appUri')

            self._dappLoadedByUri[uri] = True

    @GService.task
    async def registryTask(self):
        while not self.should_stop:
            await asyncio.sleep(180)

            await self.loadCapsulesFromSources()

    async def loadCapsulesFromSources(self):
        if self._processing:
            return

        async with self.lock:
            self._processing = True

            for n, srcdata in self.serviceConfig.registries.items():
                try:
                    sDataPath = self.rootPath.joinpath(
                        'registry').joinpath(n)
                    sDataPath.mkdir(parents=True, exist_ok=True)

                    url = srcdata.get('url')
                    enabled = srcdata.get('enabled', True)

                    if not enabled:
                        continue

                    reg = await self.registryFromUrl(url, sDataPath)

                    if reg:
                        await self.registryProcess(reg)
                except Exception:
                    continue

            self._processing = False

    async def registryProcess(self, obj):
        try:
            assert 'icapsules' in obj

            for uri, cfg in obj.icapsules.items():
                depls = cfg.get('deployments')
                dUrl = cfg.get('deploymentsUrl')

                # if uri in self._byUri or uri in self._dappLoadedByUri:
                #     continue

                # if not mtype or mtype not in ['dapp-qml', 'dapp', 'lib-qml']:
                #     continue

                if not depls:
                    continue

                log.debug(f'icapsule-registry: {uri} (durl: {dUrl})')

                # Get deployments history
                # print(dUrl)
                # depls = await self.configFromUrl(dUrl)

                ctx = await self.capsuleDeploymentsParse(uri, depls)
                if ctx:
                    self._byUri[uri] = ctx

            # Load dapps
            for uri, ctx in self._byUri.items():
                if uri in self._dappLoadedByUri:
                    continue

                if ctx.type not in ['dapp-qml', 'dapp']:
                    continue

                if len(ctx.components) > 0 and ctx.qmlEntryPoint:
                    await self.dappLoadRequest(ctx)

            return True

        except Exception:
            return False

    async def capsuleDeploymentsParse(self, uri, depls):
        try:
            version = depls.latest
            rel = depls.releases[version]
            ipfsPath = IPFSPath(rel['manifestIpfsPath'])
            assert ipfsPath.valid is True

            log.debug(f'Loading capsule from manifest: {ipfsPath}')

            return await self.loadCapsuleFromManifest(
                uri, version, ipfsPath)
        except Exception as err:
            log.debug(f'{uri}: error parsing manifest {ipfsPath}: {err}')

    async def configFromUrl(self, url: str):
        try:
            assert url is not None

            async with aiohttp.ClientSession() as sess:
                async with sess.get(url) as resp:
                    data = await resp.text()

                cfg = OmegaConf.create(data)
                assert cfg is not None
        except Exception as err:
            log.debug(f'{url}: cannot load as YAML: {err}')
        else:
            return cfg

    def registryFromArchive(self, path: Path):
        try:
            tar = tarfile.open(name=str(path))
            registry = tar.extractfile('icapsule-registry.yaml')

            return OmegaConf.create(registry.read().decode())
        except Exception:
            log.debug(f'{path}: invalid registry')

    async def registryFromUrl(self, url: str, rDataPath: Path):
        hsrc, dsrc = hashlib.sha3_256(), None
        hnew, dnew = hashlib.sha3_256(), None
        u = URL(url)

        if not u.name:
            return None

        if not u.name.endswith('.tar.gz') and not u.name.endswith('.tgz'):
            return None

        savePath = rDataPath.joinpath(u.name.lstrip('/'))

        if savePath.is_file():
            try:
                data = await asyncReadFile(str(savePath))
                hsrc.update(data)
                dsrc = hsrc.hexdigest()
            except Exception:
                pass

        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get(url) as resp:
                    data = await resp.read()
                    assert data is not None
                    hnew.update(data)
                    dnew = hnew.hexdigest()

                if dsrc and dnew and (dsrc == dnew):
                    # Same ol'
                    return self.registryFromArchive(savePath)

                fd = BytesIO(data)
                tar = tarfile.open(fileobj=fd)
                names = tar.getnames()
                assert 'icapsule-registry.yaml' in names

                await asyncWriteFile(str(savePath), data)
                registry = tar.extractfile('icapsule-registry.yaml')

                cfg = OmegaConf.create(registry.read().decode())
                assert cfg is not None
        except Exception as err:
            log.debug(f'{url}: cannot load registry: {err}')

            if savePath.is_file():
                return self.registryFromArchive(savePath)
        else:
            return cfg

    @ipfsOp
    async def loadCapsuleFromManifest(self, ipfsop,
                                      uri: str,
                                      version: str,
                                      manifestPath: IPFSPath):
        try:
            yaml = await ipfsop.catObject(str(manifestPath))
            qdef = OmegaConf.create(yaml.decode())
        except Exception as err:
            log.debug(f'loadCapsuleFromManifest: ERR {err}')
            return

        cloaded = []
        qmlEntryPoint = None
        compdefs = qdef.get('components')
        depends = qdef.get('depends')
        mtype = qdef.get('type', 'dapp-qml')

        log.debug(f'{uri}: depends {depends}')

        for cn, comp in compdefs.items():
            active = comp.get('enabled', True)
            stype = comp.get('sourceType', 'ipfs')
            ep = comp.get('qmlEntryPoint')

            if not active:
                continue

            if stype in ['localfs', 'local']:
                fspath = Path(comp.get('fsPath'))

                if ep and not qmlEntryPoint:
                    qmlEntryPoint = str(
                        fspath.joinpath('src/qml').joinpath(ep))

                if fspath:
                    cloaded.append({
                        'fsPath': str(fspath)
                    })
                continue
            elif stype in ['dweb', 'ipfs']:
                iPath = IPFSPath(comp.cid)

                rpath = self.dappsStoragePath.joinpath(uri)
                rcpath = rpath.joinpath(cn).joinpath(version)
                cpath = rcpath.joinpath(comp.cid)
                rcpath.mkdir(parents=True, exist_ok=True)

                if ep and not qmlEntryPoint:
                    qmlEntryPoint = str(cpath.joinpath('src/qml').joinpath(ep))

                if not iPath.valid:
                    continue

                if cpath.is_dir():
                    # Already loaded ?
                    cloaded.append({
                        'fsPath': str(cpath)
                    })

                    continue

                try:
                    await ipfsop.client.core.get(
                        str(iPath), dstdir=str(rcpath))
                except Exception as err:
                    log.debug(f'Could not fetch component: {iPath}: {err}')
                    continue
                else:
                    await ipfsop.pin(str(iPath))

                    cloaded.append({
                        'fsPath': str(cpath)
                    })

        return CapsuleContext(
            type=mtype,
            qdef=qdef,
            uri=uri, depends=depends,
            components=cloaded,
            qmlEntryPoint=qmlEntryPoint
        )

    async def dappLoadRequest(self, ctx):
        await self.ldPublish({
            'type': 'QmlApplicationLoadRequest',
            'appName': ctx.qdef.get('name', 'Unknown'),
            'appUri': ctx.qdef.get('uri'),
            'appIconCid': ctx.qdef.get('icon', {}).get('cid', None),
            'qmlEntryPoint': ctx.qmlEntryPoint,
            'components': ctx.components,
            'depends': ctx.depends
        })


def serviceCreate(dotPath, config, parent: GService):
    return ICapsuleRegistryLoaderService(dotPath=dotPath, config=config)
