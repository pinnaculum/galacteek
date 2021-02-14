from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor

from galacteek.browser.schemes import isIpfsUrl


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
