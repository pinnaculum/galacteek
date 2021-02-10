from PyQt5.QtWidgets import QApplication
from PyQt5.QtWebEngineWidgets import QWebEngineProfile
from PyQt5.QtWebEngineWidgets import QWebEngineSettings
from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor

from galacteek.dweb.webscripts import ethereumClientScripts

from galacteek.browser.schemes import SCHEME_DWEB
from galacteek.browser.schemes import SCHEME_ENS
from galacteek.browser.schemes import SCHEME_ENSR
from galacteek.browser.schemes import SCHEME_FS
from galacteek.browser.schemes import SCHEME_IPFS
from galacteek.browser.schemes import SCHEME_IPNS
from galacteek.browser.schemes import SCHEME_Q
# from galacteek.browser.schemes import SCHEME_GALACTEEK
from galacteek.browser.schemes import isIpfsUrl

from galacteek.config import cGet
from galacteek.config import cSet


WP_NAME_ANON = 'anonymous'
WP_NAME_MINIMAL = 'minimal'
WP_NAME_IPFS = 'ipfs'
WP_NAME_WEB3 = 'web3'


webProfilesPrio = {
    WP_NAME_MINIMAL: 0,
    WP_NAME_IPFS: 1,
    WP_NAME_WEB3: 2
}


class IPFSRequestInterceptor(QWebEngineUrlRequestInterceptor):
    """
    IPFS requests interceptor
    """

    def interceptRequest(self, info):
        url = info.requestUrl()

        if url and url.isValid() and isIpfsUrl(url):
            path = url.path()

            # Force Content-type for JS modules
            if path and path.endswith('.js'):
                info.setHttpHeader(
                    'Content-Type'.encode(),
                    'text/javascript'.encode()
                )


class BaseProfile(QWebEngineProfile):
    def __init__(self, name, config, parent=None):
        super(BaseProfile, self).__init__(
            name, parent)

        self.config = config
        self.profileName = name

        self.app = QApplication.instance()
        self.webScripts = self.scripts()
        self.webSettings = self.settings()

        self.iceptor = IPFSRequestInterceptor(self)
        self.setUrlRequestInterceptor(self.iceptor)
        self.installIpfsSchemeHandlers()
        self.installScripts()

        self.downloadRequested.connect(
            self.app.downloadsManager.onDownloadRequested)

    def installHandler(self, scheme, handler):
        sch = scheme if isinstance(scheme, bytes) else scheme.encode()
        self.installUrlSchemeHandler(sch, handler)

    def installScripts(self):
        scriptsList = self.config.get('scripts')

        if not scriptsList:
            return

        for script in scriptsList:
            if script.get('type') == 'builtin':
                if script.get('name') == 'js-ipfs-client':
                    self.installIpfsClientScript()
                elif script.get('name') == 'ethereum-web3':
                    self.installIpfsClientScript()

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
        self.installHandler(SCHEME_Q, self.app.qSchemeHandler)
        # self.installHandler(SCHEME_GALACTEEK, self.app.gSchemeHandler)

    def profileSetting(self, defaults, name, default=False):
        return self.config.settings.get(
            name,
            defaults.settings.get(name, default)
        )

    def profileJsSetting(self, defaults, name, default=False):
        return self.config.settings.javascript.get(
            name,
            defaults.settings.javascript.get(name, default)
        )

    def profileFont(self, name, default=None):
        return self.config.fonts.get(name, default)

    def configure(self, defaults={}):
        self.webSettings.setAttribute(
            QWebEngineSettings.FullScreenSupportEnabled,
            self.profileSetting(defaults, 'fullScreenSupport')
        )

        self.webSettings.setAttribute(
            QWebEngineSettings.PluginsEnabled,
            self.profileSetting(defaults, 'plugins')
        )

        self.webSettings.setAttribute(
            QWebEngineSettings.LocalStorageEnabled,
            self.profileSetting(defaults, 'localStorage', True)
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
            self.profileSetting(defaults, 'minFontSize', 12)
        )
        self.webSettings.setFontSize(
            QWebEngineSettings.DefaultFontSize,
            self.profileSetting(defaults, 'defaultFontSize', 12)
        )
        self.webSettings.setUnknownUrlSchemePolicy(
            QWebEngineSettings.DisallowUnknownUrlSchemes
        )

        cacheType = self.profileSetting(defaults, 'cacheType', 'nocache')

        if cacheType == 'nocache':
            self.setHttpCacheType(QWebEngineProfile.NoCache)
        elif cacheType == 'memory':
            self.setHttpCacheType(QWebEngineProfile.MemoryHttpCache)
        elif cacheType == 'disk':
            self.setHttpCacheType(QWebEngineProfile.DiskHttpCache)
        else:
            self.setHttpCacheType(QWebEngineProfile.NoCache)

        cookiesPolicy = self.profileSetting(
            defaults, 'cookiesPolicy', 'none')

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
            QWebEngineSettings.JavascriptEnabled,
            self.profileJsSetting(defaults, 'enabled')
        )
        self.webSettings.setAttribute(
            QWebEngineSettings.JavascriptCanOpenWindows,
            self.profileJsSetting(defaults, 'canOpenWindows')
        )
        self.webSettings.setAttribute(
            QWebEngineSettings.JavascriptCanAccessClipboard,
            self.profileJsSetting(defaults, 'canAccessClipboard')
        )

        self.webSettings.setAttribute(
            QWebEngineSettings.XSSAuditingEnabled,
            self.profileSetting(defaults, 'xssAuditing')
        )


def wpRegisterFromConfig(app):
    from galacteek.config import merge

    cfgWpList = cGet('webprofiles')

    defaults = cfgWpList.get('defaultProfile', None)

    for wpName, config in cfgWpList.items():
        if wpName == 'defaultProfile':
            continue

        if defaults:
            config = merge(config, defaults)
            cfgWpList[wpName] = config

            cSet(f'webprofiles.{wpName}', config, merge=True)

        wp = BaseProfile(wpName, config, parent=app)
        wp.configure(defaults=defaults)

        app.webProfiles[wpName] = wp
