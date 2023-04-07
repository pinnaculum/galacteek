import asyncio
import ipaddress
import traceback
from pathlib import Path
from omegaconf import OmegaConf

try:
    import adblock
except (ImportError, BaseException):
    useAdBlock = False
else:
    useAdBlock = True


from PyQt5.QtCore import QUrl
from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor
from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInfo

from galacteek import log

from galacteek.config import Configurable
from galacteek.config import cGet
from galacteek.config import cSet

from galacteek.browser.schemes import isIpfsUrl
from galacteek.browser.schemes import isEnsUrl
from galacteek.browser.schemes import SCHEME_HTTP
from galacteek.browser.schemes import SCHEME_HTTPS
from galacteek.browser.schemes import SCHEME_ENS

from galacteek.core.asynclib.fetch import assetFetch
from galacteek.core.asynclib import asyncReadFile

from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ipfs.fetch import fetchWithSpecificGateway


# https://github.com/qutebrowser/qutebrowser/blob/991cf1e8baee1a2365c1e2e81f92ce348344871c/qutebrowser/components/braveadblock.py

_RESOURCE_TYPE_STRINGS = {
    QWebEngineUrlRequestInfo.ResourceTypeMainFrame: 'main_frame',
    QWebEngineUrlRequestInfo.ResourceTypeSubFrame: 'sub_frame',
    QWebEngineUrlRequestInfo.ResourceTypeStylesheet: 'stylesheet',
    QWebEngineUrlRequestInfo.ResourceTypeScript: 'script',
    QWebEngineUrlRequestInfo.ResourceTypeImage: 'image',
    QWebEngineUrlRequestInfo.ResourceTypeFontResource: 'font',
    QWebEngineUrlRequestInfo.ResourceTypeSubResource: 'sub_frame',
    QWebEngineUrlRequestInfo.ResourceTypePluginResource: 'other',
    QWebEngineUrlRequestInfo.ResourceTypeObject: 'object',
    QWebEngineUrlRequestInfo.ResourceTypeMedia: 'media',
    QWebEngineUrlRequestInfo.ResourceTypeWorker: 'other',
    QWebEngineUrlRequestInfo.ResourceTypeSharedWorker: 'other',
    QWebEngineUrlRequestInfo.ResourceTypeServiceWorker: 'other',
    QWebEngineUrlRequestInfo.ResourceTypePrefetch: 'other',
    QWebEngineUrlRequestInfo.ResourceTypeFavicon: 'image',
    QWebEngineUrlRequestInfo.ResourceTypeXhr: 'xhr',
    QWebEngineUrlRequestInfo.ResourceTypePing: 'ping',
    None: ''
}


def _resourceTypeAsString(resource_type) -> str:
    return _RESOURCE_TYPE_STRINGS.get(resource_type, 'other')


class ResourceAccessBlocker:
    """
    adblock-based resource blocker
    """

    def __init__(self, interDataPath: Path):
        self.interDataPath = interDataPath
        self._engine = adblock.Engine(adblock.FilterSet())

    @property
    def enabled(self):
        return cGet(
            'resourceBlocker.enabled',
            mod='galacteek.services.dweb.inter'
        )

    @property
    def currentBlockListRevision(self):
        return cGet(
            'resourceBlocker.currentRevision',
            mod='galacteek.services.dweb.inter'
        )

    def setNewRevision(self, checksum: str):
        cSet(
            'resourceBlocker.currentRevision',
            checksum,
            mod='galacteek.services.dweb.inter'
        )

    def cachePathForChecksum(self, csum: str):
        return self.interDataPath.joinpath(
            f'{csum}.adblock.cache')

    async def readCache(self, cachePath: Path) -> None:
        loop = asyncio.get_event_loop()
        try:
            assert cachePath.is_file()

            # Deserialize in threadpool
            await loop.run_in_executor(
                None,
                self._engine.deserialize_from_file,
                str(cachePath)
            )
        except (OSError, AssertionError):
            return False
        except Exception as err:
            log.debug(f'cannot read from cache: {cachePath}: {err}')
            return False
        else:
            log.debug(f'Read adblock cache: {cachePath}')
            return True

    async def configure(self, cfg):
        if not self.enabled:
            return False

        loop = asyncio.get_event_loop()

        fset = adblock.FilterSet()

        fp, sourcesCsum = await assetFetch(cfg.blockListsMasterUrl)
        if not fp or not sourcesCsum:
            if self.currentBlockListRevision:
                # Try to load the current cache

                cacheOk = await self.readCache(
                    self.cachePathForChecksum(
                        self.currentBlockListRevision
                    )
                )
                if cacheOk:
                    return cacheOk

            return False

        # Path to the blocklists cache (format: <checksum>.adblock.cache)
        cSumedPath = self.interDataPath.joinpath(
            f'{sourcesCsum}.adblock.cache')

        cacheWorked = await self.readCache(cSumedPath)

        if cacheWorked:
            # Reading the checksum-dependent cache worked, we're good now
            log.debug(f'Successfully loaded adblock cache: {cSumedPath}')

            return True

        # No cache was found. Read the lists and feed the engine
        try:
            lists = OmegaConf.load(str(fp))
        except Exception:
            return False

        try:
            for provider, provider_fsets in lists.items():
                for fset_name, fset_descr in list(provider_fsets.items()):
                    sourcePath = IPFSPath(fset_descr.get('ipfsPath'))
                    if not sourcePath.valid:
                        # xxx: continue or bail out ?
                        continue

                    filtersp, lsum = await fetchWithSpecificGateway(
                        sourcePath)

                    if not filtersp:
                        # xxx: continue or bail out ?
                        continue

                    data = await asyncReadFile(str(filtersp), 'rt')
                    if data:
                        fset.add_filter_list(data)

                    filtersp.unlink()
        except Exception:
            log.debug(
                f'Adblock filters upgrade error: {traceback.format_exc()}'
            )
            return False

        self._engine = adblock.Engine(fset)

        await loop.run_in_executor(
            None,
            self._engine.serialize_to_file,
            str(cSumedPath)
        )

        self.setNewRevision(sourcesCsum)

        log.debug(f'Upgraded adblock rules to checksum: {sourcesCsum}')

        return True


class IPFSRequestInterceptor(QWebEngineUrlRequestInterceptor,
                             Configurable):
    """
    IPFS requests interceptor
    """

    def __init__(self, config, queue, dataPath: Path, parent=None):
        super(IPFSRequestInterceptor, self).__init__(parent)

        self.config = config
        self._queue = queue
        self._dataPath = dataPath
        self._urlblocker = None

    async def reconfigure(self):
        if useAdBlock:
            # Setup the resource blocker

            if not self._urlblocker:
                self._urlblocker = ResourceAccessBlocker(self._dataPath)

            return await self._urlblocker.configure(
                self.config.get('resourceBlocker')
            )

    def interceptRequest(self, info):
        url = info.requestUrl()
        firstPartyUrl = info.firstPartyUrl()

        if self._urlblocker and self._urlblocker.enabled and \
           url.scheme() in [SCHEME_HTTP, SCHEME_HTTPS]:
            # Don't try to block IPs or localhost

            firstPartyInvalid = firstPartyUrl is None or \
                not firstPartyUrl.isValid() or \
                firstPartyUrl.scheme() == "file"

            try:
                assert firstPartyInvalid is False

                ipaddress.ip_address(url.host())
                assert url.host() != 'localhost'
            except Exception:
                check = self._urlblocker._engine.check_network_urls(
                    url.toString(),
                    firstPartyUrl.toString(),
                    _resourceTypeAsString(info.resourceType())
                )

                if check.matched:
                    # Block access to this resource
                    info.block(True)

        if url.scheme() == SCHEME_HTTP:
            """
            HTTP requests with a .eth TLD get redirected
            to the ens: scheme
            """
            hparts = url.host().split('.')

            if len(hparts) > 1 and hparts[-1] == 'eth':
                rUrl = QUrl()
                rUrl.setScheme(SCHEME_ENS)
                rUrl.setHost(url.host())
                rUrl.setPath(url.path())

                if url.hasQuery():
                    rUrl.setQuery(url.query())

                return info.redirect(rUrl)
        elif isIpfsUrl(url) or isEnsUrl(url) or url.scheme() == SCHEME_HTTPS:
            path = url.path()

            # Force Content-type for JS modules
            if path and path.endswith('.js'):
                info.setHttpHeader(
                    'Content-Type'.encode(),
                    'text/javascript'.encode()
                )

            if path and path.endswith('.css'):
                info.setHttpHeader(
                    'Content-Type'.encode(),
                    'text/css'.encode()
                )
