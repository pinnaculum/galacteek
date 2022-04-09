from PyQt5.QtWidgets import QApplication
from PyQt5.QtWebEngineWidgets import QWebEngineProfile
from PyQt5.QtWebEngineWidgets import QWebEngineSettings

from PyQt5.QtWebEngine import QQuickWebEngineProfile

from galacteek.dweb.webscripts import ethereumClientScripts
from galacteek.dweb.webscripts import scriptFromQFile

from galacteek.browser.schemes import SCHEME_DWEB
from galacteek.browser.schemes import SCHEME_ENS
from galacteek.browser.schemes import SCHEME_ENSR
from galacteek.browser.schemes import SCHEME_FS
from galacteek.browser.schemes import SCHEME_I
from galacteek.browser.schemes import SCHEME_IPFS
from galacteek.browser.schemes import SCHEME_IPNS
from galacteek.browser.schemes import SCHEME_IPID
from galacteek.browser.schemes import SCHEME_QMAP
from galacteek.browser.schemes import SCHEME_MANUAL
from galacteek.browser.schemes import SCHEME_GEMINI
from galacteek.browser.schemes import SCHEME_GEMI
from galacteek.browser.schemes import SCHEME_GEM
from galacteek.browser.schemes import SCHEME_PRONTO_GRAPHS

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
        scriptsList = self.config.get('scripts')

        if not scriptsList:
            return

        for script in scriptsList:
            _type = script.get('type')

            if _type == 'builtin':
                if script.get('name') == 'js-ipfs-client':
                    self.installIpfsClientScript()
                elif script.get('name') == 'ethereum-web3':
                    self.installIpfsClientScript()
            elif _type == 'qrc':
                _name = script.get('name')
                _path = script.get('path')

                if not _name or not _path:
                    continue

                script = scriptFromQFile(_name, _path)
                if script:
                    self.webScripts.insert(script)

    def installIpfsClientScript(self):
        exSc = self.webScripts.findScript('ipfs-http-client')
        if exSc.isNull():
            for script in self.app.scriptsIpfs:
                self.webScripts.insert(script)

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
            self.installHandler(scheme, self.app.nativeIpfsSchemeHandler)

        self.installHandler(SCHEME_ENS, self.app.ensProxySchemeHandler)
        self.installHandler(SCHEME_ENSR, self.app.ensSchemeHandler)
        self.installHandler(SCHEME_QMAP, self.app.qSchemeHandler)
        self.installHandler(SCHEME_IPID, self.app.ipidSchemeHandler)
        self.installHandler(SCHEME_I, self.app.iSchemeHandler)

        self.installHandler(SCHEME_GEMINI, self.app.geminiSchemeHandler)
        self.installHandler(SCHEME_GEMI, self.app.gemIpfsSchemeHandler)
        self.installHandler(SCHEME_GEM, self.app.gemIpfsSchemeHandler)
        self.installHandler(SCHEME_PRONTO_GRAPHS,
                            self.app.prontoGSchemeHandler)

    def profileSetting2(self, defaults, name, default=False):
        return self.config.settings.get(
            name,
            defaults.settings.get(name, default)
        )

    def profileJsSetting2(self, defaults, name, default=False):
        return self.config.settings.javascript.get(
            name,
            defaults.settings.javascript.get(name, default)
        )

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

        # cacheType = self.profileSetting(defaults, 'cacheType', 'nocache')
        cacheType = profileSetting('cacheType', 'nocache')

        if cacheType == 'nocache':
            self.setHttpCacheType(QWebEngineProfile.NoCache)
        elif cacheType == 'memory':
            self.setHttpCacheType(QWebEngineProfile.MemoryHttpCache)
        elif cacheType == 'disk':
            self.setHttpCacheType(QWebEngineProfile.DiskHttpCache)
        else:
            self.setHttpCacheType(QWebEngineProfile.NoCache)

        cookiesPolicy = profileSetting('cookiesPolicy', 'none')

        if cookiesPolicy == 'none':
            self.setPersistentCookiesPolicy(
                QWebEngineProfile.NoPersistentCookies)
        elif cookiesPolicy == 'allow':
            self.setPersistentCookiesPolicy(
                QWebEngineProfile.AllowPersistentCookies)
        elif cookiesPolicy == 'force':
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

    def quickClone(self):
        # Clone the profile for usage in QML
        # (QML uses a special QQuickWebEngineProfile)

        profile = QQuickWebEngineProfile(self)
        profile.installUrlSchemeHandler(
            SCHEME_I.encode(), self.app.iSchemeHandler)

        for scheme in [SCHEME_IPFS, SCHEME_IPNS]:
            profile.installUrlSchemeHandler(
                scheme.encode(),
                self.app.nativeIpfsSchemeHandler)

        m = SCHEME_MANUAL.encode()
        manualHandler = self.urlSchemeHandler(m)

        if manualHandler:
            profile.installUrlSchemeHandler(m, manualHandler)

        return profile


def onProfilesChanged():
    app = runningApp()

    for wpName, wp in app.webProfiles.items():
        log.warning(f'Reconfiguring webprofile: {wpName}')

        wp.configure()


def wpRegisterFromConfig(app):
    """
    Initialize all the configured web profiles
    """

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
            parent=app
        )
        wp.configure()

        app.webProfiles[wpName] = wp

        cSet(f'webProfiles.{wpName}', wp.config, merge=True,
             noCallbacks=True)

    configModRegCallback(onProfilesChanged)
