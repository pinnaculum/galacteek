from PyQt5.QtNetwork import QNetworkProxy
from PyQt5.QtNetwork import QNetworkProxyFactory


class Proxy(QNetworkProxy):
    def apply(self):
        QNetworkProxy.setApplicationProxy(self)

    def url(self):
        return None


class TorNetworkProxy(QNetworkProxy):
    def __init__(self, torCfg):
        super().__init__()
        self.torCfg = torCfg

        self.setType(QNetworkProxy.Socks5Proxy)
        self.setHostName(self.torCfg.hostname)
        self.setPort(self.torCfg.socksPort)

    def url(self):
        return f'socks5://{self.torCfg.hostname}:{self.torCfg.socksPort}'


def useSystemProxyConfig(use: bool):
    QNetworkProxyFactory.setUseSystemConfiguration(use)


class NullProxy(QNetworkProxy):
    def __init__(self):
        super().__init__()
        self.setType(QNetworkProxy.NoProxy)

    def url(self):
        return None
