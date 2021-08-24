from pathlib import Path
from omegaconf import OmegaConf
import aiohttp

from galacteek import log
from galacteek.services import GService
from galacteek.ipfs import ipfsOp
from galacteek.ipfs.cidhelpers import IPFSPath


class QMLComponentsLoaderService(GService):
    """
    Service that loads QML apps from IPFS and notifies
    the application when they're ready to be used.
    """

    name = 'qmlcomponents'

    def on_init(self):
        self.dappsStoragePath = self.rootPath.joinpath('components')
        self.dappsStoragePath.mkdir(exist_ok=True, parents=True)
        self._qc = {}

    async def on_start(self):
        pass

    async def event_g_services_app(self, key, message):
        event = message['event']

        # TODO: event repo ready or peer count > 0
        if event['type'] == 'IpfsRepositoryReady':
            await self.loadAppsFromConfig()

    async def loadAppsFromConfigOld(self):
        for name, adef in self.serviceConfig.apps.items():
            await self.loadApp(name, adef)

    async def loadAppsFromConfig(self):
        for n, srcdata in self.serviceConfig.sources.items():
            url = srcdata.get('url')

            cfg = await self.configFromUrl(url)

            await self.dappsListProcess(cfg)

    async def dappsListProcess(self, obj):
        try:
            assert 'dapps' in obj

            for uri, cfg in obj.dapps.items():
                dUrl = cfg.get('deploymentsUrl')
                if not dUrl:
                    continue

                # Get deployments history
                depls = await self.configFromUrl(dUrl)

                await self.dappDeploymentsParse(uri, depls)
            return True

        except Exception:
            return False

    async def dappDeploymentsParse(self, uri, depls):
        try:
            rel = depls.releases[depls.latest]
            ipfsPath = IPFSPath(rel['manifestIpfsPath'])
            assert ipfsPath.valid is True

            log.debug(f'Loading dapp from manifestt: {ipfsPath}')

            await self.loadDappFromManifest(uri, ipfsPath)
        except Exception as err:
            print(str(err))
            return None

    async def configFromUrl(self, url: str):
        try:
            assert url is not None

            async with aiohttp.ClientSession() as sess:
                async with sess.get(url) as resp:
                    data = await resp.text()

                cfg = OmegaConf.create(data)
                assert cfg is not None
        except Exception as err:
            print(str(err))
            pass
        else:
            return cfg

    @ipfsOp
    async def loadDappFromManifest(self, ipfsop,
                                   uri: str,
                                   manifestPath: IPFSPath):
        try:
            yaml = await ipfsop.catObject(str(manifestPath))
            qdef = OmegaConf.create(yaml.decode())
        except Exception as err:
            log.debug(f'loadDappFromManifest: ERR {err}')
            return

        cloaded = []
        qmlEntryPoint = None
        compdefs = qdef.get('components')

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
                rcpath = rpath.joinpath(cn)
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
                    log.dedbug(f'Could not fetch component: {iPath}: {err}')
                    continue
                else:
                    await ipfsop.pin(str(iPath))

                    cloaded.append({
                        'fsPath': str(cpath)
                    })

        if len(cloaded) > 0 and qmlEntryPoint:
            await self.appNotify(
                qdef,
                cloaded,
                qmlEntryPoint
            )

    async def appNotify(self, appdef, comps: list, qmlEntryPoint):
        await self.ldPublish({
            'type': 'QmlApplicationLoaded',
            'appName': appdef.get('name', 'Unknown'),
            'appUri': appdef.get('uri'),
            'appIconCid': appdef.get('icon', {}).get('cid', None),
            'qmlEntryPoint': qmlEntryPoint,
            'components': comps
        })


def serviceCreate(dotPath, config, parent: GService):
    return QMLComponentsLoaderService(dotPath=dotPath, config=config)
