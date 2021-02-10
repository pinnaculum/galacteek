
from PyQt5.QtWidgets import QToolButton
from PyQt5.QtWidgets import QAction

from galacteek.core import runningApp
from galacteek.config import cSet
from galacteek.config import configModRegCallback
from galacteek.config import cModuleContext
from galacteek.qt.webengine import *
from galacteek.browser.webproxy import TorNetworkProxy

from . import PopupToolButton


class TorControllerButton(PopupToolButton):
    def __init__(self, torService, parent=None):
        super().__init__(
            parent=parent,
            mode=QToolButton.InstantPopup
        )

        self.app = runningApp()
        self.tor = torService.proc

        self.tor.torProto.sTorBootstrapStatus.connectTo(
            self.onTorBootstrapStatus)

        self.setObjectName('torControlButton')
        self.setCheckable(True)
        self.setChecked(False)

        self.enableAction = QAction(
            'Enable/disable Tor',
            self,
            triggered=self.onEnableDisable
        )
        self.enableAction.setCheckable(True)

        self.autoUseAction = QAction(
            'Automatically use Tor as proxy',
            self,
            triggered=self.onAutoUse
        )
        self.autoUseAction.setCheckable(True)

        self.configApply()

        self.menu.addAction(self.enableAction)
        self.menu.addAction(self.autoUseAction)

        configModRegCallback(self.onConfigChangedAsync,
                             mod=self.serviceConfigModule)

    @property
    def serviceConfigModule(self):
        return 'galacteek.services.net.tor'

    async def onConfigChangedAsync(self):
        self.configApply()

    def configApply(self):
        with cModuleContext(self.serviceConfigModule) as cfg:
            self.enableAction.setChecked(cfg.enabled)
            self.autoUseAction.setChecked(cfg.proxyHttpAutoUse)

        self.updateButtonStatus()

    def onEnableDisable(self, checked):
        cSet('enabled', checked, mod=self.serviceConfigModule)

    def onAutoUse(self, checked):
        cSet('proxyHttpAutoUse', checked, mod=self.serviceConfigModule)

        try:
            assert self.tor.running is True
            self.useTorProxy(use=self.tor.running and checked)
        except Exception:
            pass

    def updateButtonStatus(self):
        with cModuleContext(self.serviceConfigModule) as cfg:
            self.setChecked(cfg.enabled and cfg.proxyHttpAutoUse)

    def sysTrayMessage(self, msg):
        self.app.systemTrayMessage(
            'Tor',
            msg
        )

    def useTorProxy(self, use=True):
        if use is True and self.tor.running:
            proxy = TorNetworkProxy(self.tor.torCfg)
            self.app.networkProxySet(proxy)

            self.setToolTip(self.tt(
                f'TOR is used as proxy '
                f'(socks port: {proxy.port()})'))

            self.sysTrayMessage(
                'Tor is now used as proxy'
            )
        else:
            self.app.networkProxySetNull()
            self.app.systemTrayMessage(
                'Tor',
                'Tor is now desactivated'
            )

        self.app.allWebProfilesSetAttribute(
            QWebEngineSettings.XSSAuditingEnabled,
            use
        )
        self.app.allWebProfilesSetAttribute(
            QWebEngineSettings.DnsPrefetchEnabled,
            not use
        )

        # Always disable javascript when using tor
        if 0:
            self.app.allWebProfilesSetAttribute(
                QWebEngineSettings.JavascriptEnabled,
                not use
            )

    def onToggled(self, checked):
        self.useTorProxy(checked)

    def tt(self, message):
        return f'''
            <img src=':/share/icons/tor.png' width='32' height='32'></img>

            <p>Tor status: <b>{message}</b></p>

            <p>
                <b>Click</b> on this icon to enable/disable Tor proxying
            </p>
        '''

    async def onTorBootstrapStatus(self, pct, status):
        self.setToolTip(self.tt(f'TOR bootstrap: {pct}% complete'))

        with cModuleContext(self.serviceConfigModule) as cfg:
            if pct == 100:
                self.useTorProxy(use=cfg.proxyHttpAutoUse)

        self.updateButtonStatus()
