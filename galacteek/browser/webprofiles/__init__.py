from omegaconf import DictConfig

from PyQt5.QtWidgets import QApplication
from PyQt5.QtWebEngineWidgets import QWebEngineProfile
from PyQt5.QtWebEngineWidgets import QWebEngineSettings

from PyQt5.QtCore import QUrl
from PyQt5.QtWebEngine import QQuickWebEngineProfile

from galacteek.dweb.webscripts import ethereumClientScripts
from galacteek.dweb.webscripts import webTorrentScripts
from galacteek.dweb.webscripts import scriptFromQFile
from galacteek.dweb.webscripts import styleSheetScript
from galacteek.dweb.webscripts import ipfsFetchScript

from galacteek.browser.schemes import SCHEME_DWEB
from galacteek.browser.schemes import SCHEME_ENS
from galacteek.browser.schemes import SCHEME_ENSR
from galacteek.browser.schemes import SCHEME_FS
from galacteek.browser.schemes import SCHEME_GOPHER
from galacteek.browser.schemes import SCHEME_I
from galacteek.browser.schemes import SCHEME_IPFS
from galacteek.browser.schemes import SCHEME_IPFS_P_HTTP
from galacteek.browser.schemes import SCHEME_IPFS_P_HTTPS
from galacteek.browser.schemes import SCHEME_IPNS
from galacteek.browser.schemes import SCHEME_IPID
from galacteek.browser.schemes import SCHEME_IPS
from galacteek.browser.schemes import SCHEME_QMAP
from galacteek.browser.schemes import SCHEME_MANUAL
from galacteek.browser.schemes import SCHEME_GEMINI
from galacteek.browser.schemes import SCHEME_GEMI
from galacteek.browser.schemes import SCHEME_GEM
from galacteek.browser.schemes import SCHEME_PRONTO_GRAPHS
from galacteek.browser.schemes import SCHEME_MAGNET
from galacteek.browser.schemes import SCHEME_WEBT_STREAM_MAGNET

from galacteek import log
from galacteek.core import runningApp

from galacteek.config import cGet
from galacteek.config import cSet
from galacteek.config import configModRegCallback
from galacteek.config import merge

from galacteek.core.ps import KeyListener
from galacteek.core.ps import makeKeyService


WP_NAME_ANON = 'anonymous'
WP_NAME_MINIMAL = 'minimal'
WP_NAME_IPFS = 'ipfs'
WP_NAME_WEB3 = 'web3'


webProfilesPrio = {
    WP_NAME_MINIMAL: 0,
    WP_NAME_IPFS: 1,
    WP_NAME_WEB3: 2
}


class BaseProfile(QWebEngineProfile, KeyListener):
    def __init__(self,
                 defaultProfile,
                 name=None,
                 otr=False,
                 storageName=None,
                 styles: dict = {},
                 parent=None):
        if storageName:
            super(BaseProfile, self).__init__(
                storageName, parent=parent)
        else:
            super(BaseProfile, self).__init__(
                parent=parent)

        self.profileName = name
        self.defaults = defaultProfile

        self.app = QApplication.instance()
        self.webScripts = self.scripts()
        self.webSettings = self.settings()
        self.webStyles = styles
        self.webStyleScripts = []

        self.installIpfsSchemeHandlers()
        self.installScripts()

        self.downloadRequested.connect(
            self.app.downloadsManager.onDownloadRequested)

        # Listen to ps key: dweb.inter
        self.psListen(makeKeyService('dweb', 'inter'))

    @property
    def config(self):
        return merge(
            self.defaults,
            cGet(f'webProfiles.{self.profileName}')
        )

    async def event_g_services_dweb_inter(self, key, message):
        """
        Handles messages coming from the interceptor service
        """
        from galacteek.services.dweb.inter import InterceptorMessageTypes

        event = message['event']

        if event['type'] == InterceptorMessageTypes.Ready:
            log.debug('Interceptor ready')

            self.setUrlRequestInterceptor(event['interceptor'])

    def installHandler(self, scheme, handler):
        sch = scheme if isinstance(scheme, bytes) else scheme.encode()
        self.installUrlSchemeHandler(sch, handler)

    def installScripts(self):
        styleConfig = self.config.get('style')
        scriptsList = self.config.get('jsScripts')

        if not scriptsList:
            return

        if isinstance(styleConfig, DictConfig) and self.webStyles:
            # Style
            # TODO: day/night switching

            styleName = styleConfig.get('day')
            styleScripts = self.webStyles.get(styleName)

            if styleScripts:
                [self.webScripts.insert(script) for script in styleScripts]

                self.webStyleScripts = styleScripts

        # Webtorrent
        [self.webScripts.insert(script) for script in webTorrentScripts()]

        def scPrioFilter(sitem):
            try:
                name, sdef = sitem
                return sdef.get('priority', 100)
            except Exception:
                return 100

        oscList = sorted(
            scriptsList.items(),
            key=scPrioFilter
        )

        for scriptName, scriptDef in oscList:
            _type = scriptDef.get('type')
            _path = scriptDef.get('path')

            if _type == 'builtin':
                if scriptName == 'js-ipfs-client':
                    self.installIpfsClientScript()
                elif scriptName == 'ipfs-fetch':
                    self.installIpfsFetchScript()
                elif scriptName == 'ethereum-web3':
                    self.installWeb3Scripts()
            elif _type == 'qrc':
                if not _path:
                    continue

                script = scriptFromQFile(scriptName, _path)
                if script:
                    self.webScripts.insert(script)

    def installIpfsClientScript(self):
        exSc = self.webScripts.findScript('ipfs-http-client')
        if exSc.isNull():
            for script in self.app.scriptsIpfs:
                self.webScripts.insert(script)

    def installIpfsFetchScript(self):
        exSc = self.webScripts.findScript('ipfs-fetch')

        if exSc.isNull():
            self.webScripts.insert(
                ipfsFetchScript(self.app.getIpfsConnectionParams())
            )

    def installWeb3Scripts(self):
        ethereumScripts = ethereumClientScripts(
            self.app.getEthParams())
        if ethereumScripts:
            [self.webScripts.insert(script) for script in
             ethereumScripts]

    def installIpfsSchemeHandlers(self):
        # XXX Remove fs: soon
        for scheme in [SCHEME_DWEB, SCHEME_FS]:
            self.installHandler(scheme, self.app.dwebSchemeHandler)

        for scheme in [SCHEME_IPFS, SCHEME_IPNS]:
            self.installHandler(scheme, self.app.nativeSyncIpfsSchemeHandler)

        self.installHandler(SCHEME_ENS, self.app.ensProxySchemeHandler)
        self.installHandler(SCHEME_ENSR, self.app.ensSchemeHandler)
        self.installHandler(SCHEME_QMAP, self.app.qSchemeHandler)
        self.installHandler(SCHEME_IPID, self.app.ipidSchemeHandler)
        self.installHandler(SCHEME_IPS, self.app.ipsSchemeHandler)
        self.installHandler(SCHEME_I, self.app.iSchemeHandler)
        self.installHandler(SCHEME_IPFS_P_HTTP,
                            self.app.ipfsHttpSchemeHandler)
        self.installHandler(SCHEME_IPFS_P_HTTPS,
                            self.app.ipfsHttpSchemeHandler)

        self.installHandler(SCHEME_GEMINI, self.app.geminiSchemeHandler)
        self.installHandler(SCHEME_GEMI, self.app.gemIpfsSchemeHandler)
        self.installHandler(SCHEME_GEM, self.app.gemIpfsSchemeHandler)
        self.installHandler(SCHEME_PRONTO_GRAPHS,
                            self.app.prontoGSchemeHandler)
        self.installHandler(SCHEME_WEBT_STREAM_MAGNET,
                            self.app.webTorrentSchemeHandler)
        self.installHandler(SCHEME_MAGNET,
                            self.app.webTorrentSchemeHandler)
        self.installHandler(SCHEME_GOPHER,
                            self.app.gopherSchemeHandler)

    def profileFont(self, name, default=None):
        return self.config.fonts.get(name, default)

    def configure(self):
        config = self.config
        defaults = self.defaults

        def profileSetting(name, default=False):
            return config.settings.get(
                name,
                defaults.settings.get(name, default)
            )

        def profileJsSetting(name, default=False):
            return config.settings.javascript.get(
                name,
                defaults.settings.javascript.get(name, default)
            )

        self.webSettings.setAttribute(
            QWebEngineSettings.FullScreenSupportEnabled,
            profileSetting('fullScreenSupport')
        )

        self.webSettings.setAttribute(
            QWebEngineSettings.PluginsEnabled,
            profileSetting('plugins')
        )

        self.webSettings.setAttribute(
            QWebEngineSettings.PdfViewerEnabled,
            profileSetting('pdfViewerInternal')
        )

        self.webSettings.setAttribute(
            QWebEngineSettings.LocalStorageEnabled,
            profileSetting('localStorage', True)
        )

        self.webSettings.setFontFamily(
            QWebEngineSettings.StandardFont,
            self.profileFont('standard')
        )
        self.webSettings.setFontFamily(
            QWebEngineSettings.FixedFont,
            self.profileFont('fixed')
        )
        self.webSettings.setFontFamily(
            QWebEngineSettings.SerifFont,
            self.profileFont('serif')
        )
        self.webSettings.setFontSize(
            QWebEngineSettings.MinimumFontSize,
            profileSetting('minFontSize', 12)
        )
        self.webSettings.setFontSize(
            QWebEngineSettings.DefaultFontSize,
            profileSetting('defaultFontSize', 12)
        )
        self.webSettings.setUnknownUrlSchemePolicy(
            QWebEngineSettings.DisallowUnknownUrlSchemes
        )

        cacheType = profileSetting('cacheType', 'nocache')
        cacheMaxSizeMb = profileSetting('cacheMaxSizeMb', 0)

        if cacheType == 'nocache':
            self.setHttpCacheType(QWebEngineProfile.NoCache)
        elif cacheType == 'memory':
            self.setHttpCacheType(QWebEngineProfile.MemoryHttpCache)
        elif cacheType == 'disk':
            self.setHttpCacheType(QWebEngineProfile.DiskHttpCache)
        else:
            self.setHttpCacheType(QWebEngineProfile.NoCache)

        if isinstance(cacheMaxSizeMb, int) and cacheMaxSizeMb > 0:
            self.setHttpCacheMaximumSize(cacheMaxSizeMb * (1024 * 1024))

        cookiesPolicy = profileSetting('cookiesPolicy', 'none')

        if cookiesPolicy in ['none', 'deny'] or not cookiesPolicy:
            self.setPersistentCookiesPolicy(
                QWebEngineProfile.NoPersistentCookies)
        elif cookiesPolicy == 'allow':
            self.setPersistentCookiesPolicy(
                QWebEngineProfile.AllowPersistentCookies)
        elif cookiesPolicy in ['force',
                               'force-persistent']:
            self.setPersistentCookiesPolicy(
                QWebEngineProfile.ForcePersistentCookies)

        self.webSettings.setAttribute(
            QWebEngineSettings.XSSAuditingEnabled,
            profileSetting('xssAuditing')
        )
        self.webSettings.setAttribute(
            QWebEngineSettings.LocalContentCanAccessRemoteUrls,
            profileSetting('localContentCanAccessRemoteUrls')
        )
        self.webSettings.setAttribute(
            QWebEngineSettings.FocusOnNavigationEnabled,
            profileSetting('focusOnNavigation')
        )
        self.webSettings.setAttribute(
            QWebEngineSettings.WebGLEnabled,
            profileSetting('webGL')
        )
        self.webSettings.setAttribute(
            QWebEngineSettings.Accelerated2dCanvasEnabled,
            profileSetting('accelerated2dCanvas')
        )

        self.webSettings.setAttribute(
            QWebEngineSettings.JavascriptEnabled,
            profileJsSetting('enabled')
        )
        self.webSettings.setAttribute(
            QWebEngineSettings.JavascriptCanOpenWindows,
            profileJsSetting('canOpenWindows')
        )
        self.webSettings.setAttribute(
            QWebEngineSettings.JavascriptCanAccessClipboard,
            profileJsSetting('canAccessClipboard')
        )

        log.debug(f'Configured profile: {self.profileName}: '
                  f'Storage path: {self.persistentStoragePath()}')

    def installHandlerForProfile(self,
                                 profile: QWebEngineProfile,
                                 schemeName: str) -> None:
        """
        Install a URL scheme handler for a given profile and scheme.
        The scheme must already have been registered.
        """

        handler = self.urlSchemeHandler(schemeName.encode())

        if handler:
            profile.installUrlSchemeHandler(
                schemeName.encode(),
                handler
            )

    def quickClone(self) -> QQuickWebEngineProfile:
        """
        Clone this profile for usage in QML
        (QML uses a special QQuickWebEngineProfile)
        """

        # URL Schemes we install on the profile

        schemes = [SCHEME_GEMINI,
                   SCHEME_GEMI,
                   SCHEME_GOPHER,
                   SCHEME_MANUAL,
                   SCHEME_I,
                   SCHEME_IPFS,
                   SCHEME_IPNS,
                   SCHEME_IPFS_P_HTTP,
                   SCHEME_IPFS_P_HTTPS,
                   SCHEME_IPID,
                   SCHEME_DWEB,
                   SCHEME_ENS,
                   SCHEME_ENSR,
                   SCHEME_PRONTO_GRAPHS]

        profile = QQuickWebEngineProfile(self)
        profile.setDownloadPath(self.downloadPath())
        profile.setStorageName(self.storageName())

        # Install these schemes on the QQuickWebEngineProfile

        [self.installHandlerForProfile(profile, scheme)
         for scheme in schemes]

        return profile


def onProfilesChanged():
    app = runningApp()

    for wpName, wp in app.webProfiles.items():
        log.warning(f'Reconfiguring webprofile: {wpName}')

        wp.configure()


def wpParseStyles(styles: DictConfig):
    # Parse the 'styles' dictionary

    stl = {}
    for styleName, styleDef in styles.items():
        try:
            src = styleDef.get('src')
            styleName = styleDef.get('styleName')

            assert isinstance(src, str)
            assert isinstance(styleName, str)

            script = styleSheetScript(styleName, QUrl(src))
            assert script is not None  # weak

            if styleName not in stl:
                stl[styleName] = script
        except Exception:
            continue

    return stl


def wpRegisterFromConfig(app):
    """
    Initialize all the configured web profiles
    """

    # Style Scripts
    webEngineStyles = wpParseStyles(
        cGet('styles.webEngine', mod='galacteek.browser.styles')
    )

    cfgWpList = cGet('webProfiles')

    defaults = cfgWpList.get('defaultProfile')

    for wpName, config in cfgWpList.items():
        if wpName == 'defaultProfile':
            continue

        otr = cGet(f'webProfiles.{wpName}.settings.offTheRecord')
        sName = cGet(f'webProfiles.{wpName}.storageName')

        wp = BaseProfile(
            defaults,
            otr=True if otr else False,
            storageName=sName,
            name=wpName,
            parent=app,
            styles=webEngineStyles
        )
        wp.configure()

        app.webProfiles[wpName] = wp

        cSet(f'webProfiles.{wpName}', wp.config, merge=True,
             noCallbacks=True)

    configModRegCallback(onProfilesChanged)
