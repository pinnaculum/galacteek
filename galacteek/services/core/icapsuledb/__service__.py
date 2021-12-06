from pathlib import Path
from omegaconf import OmegaConf
import attr
import asyncio
import aiohttp
import tarfile
import hashlib
import traceback
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


def depends(registry, uri: str, v: str):
    try:
        dpls = registry['icapsules'][uri]['deployments']
        releases = dpls['releases']
        if v == 'latest':
            version = dpls['latest']
        else:
            version = v
        rl = releases.get(version, None)
    except Exception:
        pass
    else:
        deps = rl['manifest'].get('depends', [])

        for dep in deps:
            try:
                depdpls = registry['icapsules'][dep['uri']]['deployments']
            except Exception:
                continue

            yield {
                'uri': dep['uri'],
                'version': dep['version'],
                'deployments': depdpls
            }
            yield from depends(registry, dep['uri'], dep['version'])

        yield {
            'uri': uri,
            'version': version,
            'deployments': dpls
        }


class ICapsuleRegistryLoaderService(GService):
    """
    Service that loads QML apps from IPFS and notifies
    the application when they're ready to be used.
    """

    name = 'qmlcomponents'

    def on_init(self):
        self.lock = asyncio.Lock()
        self.dappsStoragePath = self.rootPath.joinpath('capsules')
        self.dappsStoragePath.mkdir(exist_ok=True, parents=True)
        self._qc = {}
        self._byUri = {}
        self._dappLoadedByUri = {}
        self._processing = False

    @property
    def dappsProfile(self):
        return DappsUserProfile(
            self,
            self.serviceConfig.profile
        )

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

    async def registryProcess(self, registry):
        try:
            assert 'icapsules' in registry

            return await self.dappsProfile.installFromRegistry(registry)
        except Exception:
            traceback.print_exc()
            return False

    async def capsuleDeploymentsParse(self, uri, depls):
        try:
            version = depls.latest
            rel = depls.releases[version]
            manifest = rel.get('manifest')

            ipfsPath = IPFSPath(rel['manifestIpfsPath'])
            # assert ipfsPath.valid is True

            log.debug(f'Loading capsule from manifest: {ipfsPath}')

            return await self.loadCapsuleFromManifest(
                uri, version, manifest if manifest else ipfsPath)
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
                                      manifestArg):
        if isinstance(manifestArg, IPFSPath):
            try:
                yaml = await ipfsop.catObject(str(manifestArg))
                qdef = OmegaConf.create(yaml.decode())
            except Exception as err:
                log.debug(f'loadCapsuleFromManifest: ERR {err}')
                return
        else:
            qdef = manifestArg

        cloaded = []
        qmlEntryPoint = None
        compdefs = qdef.get('components')
        depends = qdef.get('depends', [])
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
                    log.debug(f'capsule {uri}: Fetching {iPath} to {rcpath}')

                    success = False
                    async for status in ipfsop.pin2(str(iPath),
                                                    timeout=60 * 10):
                        if status[1] == 1:
                            success = True
                        elif status[1] == 0:
                            p = status[2]
                            if isinstance(p, int):
                                log.debug(
                                    f'capsule {uri}: '
                                    f'{iPath}: nodes pinned: {p}')
                        elif status[1] == -1:
                            raise Exception(f'{uri}: failed to pin!')

                    assert success is True

                    await ipfsop.client.core.get(
                        str(iPath), dstdir=str(rcpath))

                    log.debug(f'capsule {uri}: Fetch finished')

                except Exception as err:
                    log.debug(f'Could not fetch component: {iPath}: {err}')

                    return None
                else:
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


class DappsUserProfile:
    def __init__(self,
                 service: ICapsuleRegistryLoaderService,
                 cfg):
        self.service = service
        self.cfg = cfg

    async def depsInstall(self, deps):
        for dep in deps:
            depUri = dep['uri']
            cap = self.service.capsuleCtx(depUri)
            if cap:
                continue

            ctx = await self.service.capsuleDeploymentsParse(
                depUri, dep['deployments'])
            if ctx:
                self.service._byUri[depUri] = ctx
            else:
                log.debug(f'{depUri}: capsule failed to load')
                return False

        return True

    async def installFromRegistry(self, registry):
        capscfg = self.cfg.icapsulesByUri

        for uri, cfg in capscfg.items():
            installv = cfg.get('install')
            if not installv:
                continue

            deps = list(depends(registry, uri, installv))

            capok = await self.depsInstall(deps)
            if capok is False:
                log.debug(f'{uri}: FAILED to load capsule dependencies')
                continue

            if uri in self.service._dappLoadedByUri:
                continue

            ctx = self.service.capsuleCtx(uri)
            if ctx.type not in ['dapp-qml', 'dapp']:
                continue

            if len(ctx.components) > 0 and ctx.qmlEntryPoint:
                await self.service.dappLoadRequest(ctx)


def serviceCreate(dotPath, config, parent: GService):
    return ICapsuleRegistryLoaderService(dotPath=dotPath, config=config)
