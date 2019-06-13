import re

from PyQt5.QtWebEngineCore import QWebEngineUrlSchemeHandler
from PyQt5.QtWebEngineCore import QWebEngineUrlScheme
from PyQt5.QtCore import QUrl

from galacteek import log

from yarl import URL


SCHEME_DWEB = 'dweb'
SCHEME_FS = 'fs'
SCHEME_IPFS = 'ipfs'


def initializeSchemes():
    name = QWebEngineUrlScheme.schemeByName(SCHEME_DWEB.encode()).name()
    if name:
        return

    schemeDweb = QWebEngineUrlScheme(SCHEME_DWEB.encode())
    schemeDweb.setFlags(QWebEngineUrlScheme.SecureScheme)

    schemeFs = QWebEngineUrlScheme(SCHEME_FS.encode())
    schemeFs.setFlags(QWebEngineUrlScheme.SecureScheme)

    schemeIpfs = QWebEngineUrlScheme(SCHEME_IPFS.encode())
    schemeIpfs.setFlags(QWebEngineUrlScheme.SecureScheme)

    QWebEngineUrlScheme.registerScheme(schemeDweb)
    QWebEngineUrlScheme.registerScheme(schemeFs)
    QWebEngineUrlScheme.registerScheme(schemeIpfs)


class Base32IPFSSchemeHandler(QWebEngineUrlSchemeHandler):
    """
    TODO
    """
    pass


class DWebSchemeHandler(QWebEngineUrlSchemeHandler):
    """
    IPFS dweb scheme handler, supporting URLs such as:

        dweb:/ipfs/multihash
        dweb:/ipns/domain.com/path
        dweb://ipfs/multihash/...
        fs:/ipfs/multihash
        etc..
    """

    def __init__(self, app, parent=None):
        QWebEngineUrlSchemeHandler.__init__(self, parent)
        self.app = app

    def redirectIpfs(self, request, path, url):
        yUrl = URL(url.toString())
        if len(yUrl.parts) < 3:
            return None

        newUrl = self.app.subUrl(path)

        if url.hasFragment():
            newUrl.setFragment(url.fragment())
        if url.hasQuery():
            newUrl.setQuery(url.query())

        return request.redirect(newUrl)

    def requestStarted(self, request):
        url = request.requestUrl()

        if url is None:
            return

        scheme = url.scheme()

        if scheme in [SCHEME_FS, SCHEME_DWEB]:
            # Take leading slashes out of the way
            urlStr = url.toString()
            urlStr = re.sub(
                r'^{scheme}:(\/)+'.format(scheme=scheme),
                '{scheme}:/'.format(scheme=scheme),
                urlStr
            )
            url = QUrl(urlStr)
        else:
            log.debug('Unsupported scheme')
            return

        path = url.path()
        if not isinstance(path, str):
            return

        log.debug(
            'IPFS scheme handler req: {url} {scheme} {path} {method}'.format(
                url=url.toString(), scheme=scheme, path=path,
                method=request.requestMethod()))

        if path.startswith('/ipfs/') or path.startswith('/ipns/'):
            try:
                return self.redirectIpfs(request, path, url)
            except Exception as err:
                log.debug('Exception handling request: {}'.format(str(err)))
