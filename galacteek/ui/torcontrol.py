
from galacteek.core import runningApp
from galacteek.qt.webengine import *
from galacteek.browser.webproxy import TorNetworkProxy

from PyQt5.QtWidgets import QToolButton


class TorControllerButton(QToolButton):
    def __init__(self, torService, *args, **kw):
        super().__init__(*args, **kw)

        self.app = runningApp()
        self.tor = torService.proc

        self.tor.torProto.sTorBootstrapStatus.connectTo(
            self.onTorBootstrapStatus)

        self.setObjectName('torControlButton')
        self.setCheckable(True)
        self.setChecked(False)
        self.setEnabled(False)

        self.toggled.connect(self.onToggled)

    def sysTrayMessage(self, msg):
        self.app.systemTrayMessage(
            'Tor',
            msg
        )

    def useTorProxy(self, use=True):
        if use is True:
            proxy = TorNetworkProxy(self.tor.torCfg)
            self.app.networkProxySet(proxy)

            self.setToolTip(self.tt(
                f'TOR is used as proxy '
                f'(socks port: {proxy.port()})'))

            self.sysTrayMessage(
                'Tor is now used as proxy (click on the onion to disable it)'
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

        if pct == 100:
            self.setEnabled(True)
            self.sysTrayMessage(
                'Tor is ready, click on the onion to enable it'
            )
