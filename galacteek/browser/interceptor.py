
from PyQt5.QtCore import QUrl
from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor

from galacteek.config import Configurable
from galacteek.browser.schemes import isIpfsUrl
from galacteek.browser.schemes import SCHEME_HTTP
from galacteek.browser.schemes import SCHEME_ENS


class IPFSRequestInterceptor(QWebEngineUrlRequestInterceptor,
                             Configurable):
    """
    IPFS requests interceptor
    """

    def __init__(self, config, queue, parent=None):
        super(IPFSRequestInterceptor, self).__init__(parent)

        self.config = config
        self._queue = queue

    def interceptRequest(self, info):
        url = info.requestUrl()

        if not url or not url.isValid():
            return

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
        elif isIpfsUrl(url):
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

            if self._queue.full():
                # Don't overflow
                try:
                    [self._queue.get_nowait() for z in range(len(self._queue))]
                except Exception:
                    pass

            self._queue.put_nowait((url, info))
