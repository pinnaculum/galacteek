from pathlib import Path
from omegaconf import OmegaConf

from rdflib import URIRef
from rdflib import RDF

import attr
import asyncio
import aiohttp
import tarfile
import hashlib
import traceback

from io import BytesIO
from yarl import URL

from galacteek import log
from galacteek import ensure
from galacteek import cached_property

from galacteek.browser.schemes import SCHEME_I

from galacteek.core.asynclib import asyncWriteFile
from galacteek.core.asynclib import asyncReadFile

from galacteek.ld import gLdDefaultContext
from galacteek.ld.rdf import BaseGraph
from galacteek.ld.iri import urnParse
from galacteek.ld.iri import urnFsFormat

from galacteek.services import GService
from galacteek.services import getByDotName

from galacteek.ipfs import ipfsOp
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ipfs.fetch import fetchWithRandomGateway

from . import ldregistry


@attr.s(auto_attribs=True)
class CapsuleContext:
    uri: str = ''
    type: str = ''
    description: str = ''
    name: str = ''
    iconCid: str = ''

    depends: list = []
    components: list = []
    qmlEntryPoint: str = ''


allowedCapsuleTypes = [
    'dapp-qml',
    'dapp',
    'lib-qml',
    'jinja2-scheme-templates',
    'jinja2-templates'
]


def mTerm(attr: str):
    return URIRef(f'ips://galacteek.ld/ICapsuleManifest#{attr}')


def capTerm(attr: str):
    return URIRef(f'ips://galacteek.ld/ICapsule#{attr}')


def compTerm(attr: str):
    return URIRef(f'ips://galacteek.ld/ICapsuleComponent#{attr}')


class ICapsuleRegistryLoaderService(GService):
    """
    Service that loads QML apps from IPFS and notifies
    the application when they're ready to be used.
    """

    name = 'icapsuleregistry'

    def on_init(self):
        self.lock = asyncio.Lock()
        self.dappsStoragePath = self.rootPath.joinpath('capsules')
        self.dappsStoragePath.mkdir(exist_ok=True, parents=True)

        self._byUri = {}
        self._dappLoadedByUri = {}
        self._processing = False

    @property
    def pronto(self):
        return getByDotName('ld.pronto')

    @property
    def registryBranch(self):
        return self.app.cmdArgs.icapRegBranch

    @property
    def regUriRoot(self):
        return f'urn:ipg:icapsules:registries:galacteek:{self.registryBranch}'

    @property
    def graphRegistryRoot(self):
        return self.pronto.graphByUri(self.regUriRoot)

    @cached_property
    def querier(self):
        return ldregistry.ICRQuerier(self.graphRegistryRoot)

    @cached_property
    def profile(self):
        return DappsUserProfile(
            self,
            self.serviceConfig.profile
        )

    def capsuleCtx(self, uri: str):
        return self._byUri.get(uri)

    def capsuleResource(self, icapid: URIRef):
        return self.graphRegistryRoot.resource(icapid)

    async def on_start(self):
        pass

    async def mergeRegistry(self, graph: BaseGraph,
                            dstUri='urn:ipg:icapsules:registries:default'):
        dg = self.pronto.graphByUri(dstUri)

        if dg is not None:
            return await dg.guardian.mergeReplace(graph, dg)

        return False

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

        def regsort(it):
            try:
                return it[1]['priority']
            except Exception:
                return 100

        async with self.lock:
            self._processing = True

            registries = sorted(
                self.serviceConfig.icapregs.items(),
                key=regsort
            )

            for n, regcfg in registries:
                urn = urnParse(regcfg.urn)

                if not urn:
                    continue

                try:
                    sDataPath = self.rootPath.joinpath(
                        'registry').joinpath(urnFsFormat(regcfg.urn))
                    sDataPath.mkdir(parents=True, exist_ok=True)

                    url = regcfg.get('regUrl')
                    enabled = regcfg.get('enabled', True)
                    graphUri = regcfg.get(
                        'regGraphUri',
                        self.regUriRoot
                        # 'urn:ipg:icapsules:registries:default'
                    )

                    if not enabled:
                        continue

                    await self.registryFromUrl(
                        url,
                        graphUri,
                        sDataPath
                    )
                except Exception:
                    traceback.print_exc()
                    continue

            await self.profileRun()

            self._processing = False

    async def profileRun(self):
        try:
            return await self.profile.installFromConfig()
        except Exception:
            traceback.print_exc()
            return False

    async def capsuleInstallFromRef(self, icapid: URIRef):
        cloaded = []
        qmlEntryPoint = None

        try:
            depends = await self.querier.capsuleDependencies(icapid)

            # icap = self.graphRegistryRoot.resource(icapid)
            icap = self.capsuleResource(icapid)

            manifest = icap.value(capTerm('manifest'))

            if not manifest:
                raise ValueError(f'manifest not found for icapsule {icapid}')

            assert manifest is not None

            name = str(manifest.value(mTerm('name')))
            description = str(manifest.value(mTerm('description')))
            mtype = str(manifest.value(mTerm('capsuleType')))
            iconCid = str(manifest.value(mTerm('iconIpfsPath')))
            # httpGws = str(manifest.value(mTerm('ipfsHttpGws')))

            comps = await self.querier.capsuleComponents(
                icapid
            )

            for compUri in comps:
                comp = self.graphRegistryRoot.resource(compUri)

                stype = str(comp.value(compTerm('sourceType')))

                fspath = Path(str(comp.value(compTerm('fsPath'))))
                ep = str(comp.value(compTerm('qmlEntryPoint')))

                if stype in ['localfs', 'local']:
                    if ep and not qmlEntryPoint:
                        qmlEntryPoint = str(
                            fspath.joinpath('qml').joinpath(ep))

                    if fspath:
                        cloaded.append({
                            'fsPath': str(fspath)
                        })
                    continue
                elif stype in ['dweb', 'ipfs']:
                    cid = str(comp.value(compTerm('cid')))

                    if not cid:
                        log.debug(f'icapsule {icapid}: '
                                  f'component {compUri} has no CID')
                        continue

                    iPath = IPFSPath(cid)

                    # Use urnFsFormat
                    rpath = self.dappsStoragePath.joinpath(
                        urnFsFormat(icapid))
                    rcpath = rpath.joinpath(urnFsFormat(comp.identifier))
                    cpath = rcpath.joinpath(cid)
                    rcpath.mkdir(parents=True, exist_ok=True)

                    if ep and not qmlEntryPoint:
                        qmlEntryPoint = str(
                            cpath.joinpath('qml').joinpath(ep))

                    if not iPath.valid:
                        continue

                    if cpath.is_dir():
                        # Already installed

                        cloaded.append({
                            'fsPath': str(cpath)
                        })

                        continue

                    log.info(f'icapsule {icapid}: Fetching: {iPath}')

                    result = await self.capsuleExtractFromPath(iPath, cpath)
                    if result is True:
                        cloaded.append({
                            'fsPath': str(cpath)
                        })

                        # Pin in the background
                        ensure(self.pinCapsule(icapid, iPath))

                        continue
                    else:
                        raise Exception(
                            f'Capsule {icapid}: extraction from '
                            f'object {iPath} failed'
                        )

            ctx = CapsuleContext(
                type=mtype,
                name=name,
                description=description,
                uri=str(icapid),
                iconCid=iconCid,
                depends=depends,
                components=cloaded,
                qmlEntryPoint=qmlEntryPoint
            )
            self._byUri[str(icapid)] = ctx
            return ctx
        except Exception as err:
            traceback.print_exc()
            log.debug(f'{icapid}: error installing capsule: {err}')

    def registryFromArchive(self, path: Path):
        try:
            tar = tarfile.open(name=str(path))
            registry = tar.extractfile('icapsule-registry.yaml')

            return OmegaConf.create(registry.read().decode())
        except Exception:
            log.debug(f'{path}: invalid registry')

    @ipfsOp
    async def registryRdfify(self, ipfsop, regYaml):
        try:
            async with ipfsop.ldOps() as ld:
                json = OmegaConf.to_container(regYaml)

                json['@context'] = gLdDefaultContext
                g = await ld.rdfify(json)

                assert g is not None

                return g
        except Exception as err:
            log.debug(f'registry_rdfify: {err}')

    @ipfsOp
    async def registryFromUrl(self, ipfsop, url: str,
                              regGraphUri: str,
                              rDataPath: Path):
        hsrc, dsrc = hashlib.sha3_256(), None
        hnew, dnew = hashlib.sha3_256(), None
        u = URL(url)

        dstGraph = self.pronto.graphByUri(regGraphUri)
        if dstGraph is None:
            return None

        if not u.name:
            return None

        if u.scheme == 'file':
            try:
                content = await asyncReadFile(u.path, mode='rt')
                if content:
                    cfg = OmegaConf.create(content)
                else:
                    raise ValueError(f'{u.path}: not found')

                g = await self.registryRdfify(cfg)

                if 0:
                    regs = list(g.subjects(
                        predicate=RDF.type,
                        object='ips://galacteek.ld/ICapsulesRegistry'
                    ))
                    print(regs)

                await self.graphRegistryRoot.guardian.mergeReplace(
                    g,
                    dstGraph
                )

            except Exception:
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
                async with sess.get(url,
                                    verify_ssl=self.app.sslverify) as resp:
                    data = await resp.read()
                    assert data is not None
                    hnew.update(data)
                    dnew = hnew.hexdigest()

                if dsrc and dnew and (dsrc == dnew):
                    # Same ol'
                    cfg = self.registryFromArchive(savePath)
                else:
                    fd = BytesIO(data)
                    tar = tarfile.open(fileobj=fd)
                    names = tar.getnames()
                    assert 'icapsule-registry.yaml' in names

                    await asyncWriteFile(str(savePath), data)
                    registry = tar.extractfile('icapsule-registry.yaml')

                    cfg = OmegaConf.create(registry.read().decode())

                assert cfg is not None
        except Exception as err:
            log.info(f'{url}: cannot load registry: {err}')

            if savePath.is_file():
                return self.registryFromArchive(savePath)
        else:
            g = await self.registryRdfify(cfg)

            await self.graphRegistryRoot.guardian.mergeReplace(
                g,
                dstGraph
            )

            return cfg

    async def capsuleExtractFromPath(self,
                                     cIpfsPath: IPFSPath,
                                     dstdir: Path,
                                     maxArchiveSize=1024 * 1024 * 8,
                                     chunkSize=32768,
                                     maxAttempts=5):
        """
        Pull the capsule archive from the given `url`, and
        extract it to `dstdir`.

        :rtype: bool
        """

        for attempt in range(0, maxAttempts):
            fp, _s = await fetchWithRandomGateway(
                cIpfsPath,
                maxSize=maxArchiveSize
            )

            if not fp:
                log.debug(
                    f'icapextract {cIpfsPath} (attempt {attempt}): failed'
                )
                continue
            else:
                log.info(
                    f'icapextract {cIpfsPath} (attempt {attempt}): Fetch OK!'
                )

            try:
                tar = tarfile.open(str(fp))
                tar.extractall(str(dstdir))
                tar.close()
            except Exception as err:
                log.debug(
                    f'icapextract {cIpfsPath} (attempt {attempt}): '
                    f'extract failed: {err}'
                )
                continue
            else:
                log.info(
                    f'icapextract {cIpfsPath} (attempt {attempt}): Success'
                )

                try:
                    fp.unlink()
                except Exception:
                    pass

                return True

        return False

    @ipfsOp
    async def pinCapsule(self, ipfsop,
                         uri: str,
                         iPath: IPFSPath):
        try:
            success = False
            p, pPrev = 0, 0

            async for status in ipfsop.pin2(str(iPath),
                                            timeout=60 * 5):
                if status[1] == 1:
                    log.info(f'capsule {uri}: {iPath}: pin success')
                    success = True
                elif status[1] == 0:
                    p = status[2]

                    if isinstance(p, int) and pPrev != p:
                        log.info(
                            f'capsule {uri}: '
                            f'{iPath}: nodes pinned: {p}')
                        pPrev = p
                elif status[1] == -1:
                    log.info(f'capsule {uri}: {iPath}: pin failure')
                    raise Exception(f'{uri}: failed to pin!')

            assert success is True

            log.info(f'capsule {uri}: Pinned')

            return True

        except Exception as err:
            log.debug(f'Could not pin capsule: {iPath}: {err}')
            return False

    async def dappLoadRequest(self, ctx, settings: dict):
        await self.ldPublish({
            'type': 'QmlApplicationLoadRequest',
            'appName': ctx.name,
            'appUri': ctx.uri,
            'appIconCid': ctx.iconCid,
            'qmlEntryPoint': ctx.qmlEntryPoint,
            'components': ctx.components,
            'description': ctx.description,
            'depends': ctx.depends,
            'runSettings': settings
        })


class DappsUserProfile:
    def __init__(self,
                 service: ICapsuleRegistryLoaderService,
                 cfg):
        self.service = service
        self.cfg = cfg

    @property
    def iSchemeService(self):
        return getByDotName('dweb.schemes.i')

    async def depsInstall(self, deps):
        for dep in deps:
            depUri = URIRef(dep['id'])

            cap = self.service.capsuleCtx(str(depUri))
            if cap:
                continue

            ctx = await self.service.capsuleInstallFromRef(depUri)

            if not ctx:
                log.debug(f'{depUri}: capsule failed to load')
                return False

            # Post-install
            if ctx.type in ['jinja2-scheme-templates', 'jinja2-templates']:
                try:
                    paths = [comp['fsPath'] for comp in ctx.components]
                    assert len(paths) > 0

                    icap = self.service.capsuleResource(depUri)
                    manifest = icap.value(capTerm('manifest'))
                    forScheme = manifest.value(
                        mTerm('templatesForUrlScheme')
                    )

                    if not forScheme or str(forScheme) == SCHEME_I:
                        log.debug(
                            f'{depUri}: Templates for scheme: {forScheme}'
                        )

                        self.iSchemeService.jinjaEnvFromPath(paths)
                except Exception as err:
                    log.debug(f'{depUri}: failed to install templates: {err}')

        return True

    async def installCapsule(self, capsuleUri: URIRef,
                             load=True,
                             wsSwitch=False):
        uri = str(capsuleUri)

        if uri in self.service._dappLoadedByUri:
            return False

        deps = await self.service.querier.capsuleDependencies(capsuleUri)

        capok = await self.depsInstall(deps)
        if capok is False:
            log.debug(f'{uri}: FAILED to load capsule dependencies')
            return False

        ctx = await self.service.capsuleInstallFromRef(
            capsuleUri
        )

        if not ctx:
            log.debug(f'{uri}: failed to get capsule context')
            return False

        if ctx.type not in allowedCapsuleTypes:
            return False

        if len(ctx.components) > 0 and ctx.qmlEntryPoint and load is True:
            await self.service.dappLoadRequest(ctx, {
                'wsSwitch': wsSwitch
            })

    async def installFromConfig(self):
        capscfg = self.cfg.get('manifestsByUri', {})

        for manuri, cfg in capscfg.items():
            installv = cfg.get('install')

            if not installv:
                continue

            if installv == 'latest':
                latest = await self.service.querier.latestCapsule(
                    URIRef(manuri)
                )

                if not latest:
                    continue

                uri = latest
            elif ldregistry.parseVersion(installv) is not None:
                uri = f'{manuri}:{installv}'

            if uri in self.service._dappLoadedByUri:
                continue

            await self.installCapsule(
                URIRef(uri),
                load=cfg.get('autoload', False),
                wsSwitch=cfg.get('wsSwitchOnLoad', False)
            )


def serviceCreate(dotPath, config, parent: GService):
    return ICapsuleRegistryLoaderService(dotPath=dotPath, config=config)
