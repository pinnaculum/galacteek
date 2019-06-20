import uuid
import re

from PyQt5.QtWebEngineCore import QWebEngineUrlSchemeHandler
from PyQt5.QtWebEngineCore import QWebEngineUrlScheme
from PyQt5.QtWebEngineCore import QWebEngineUrlRequestJob
from PyQt5.QtCore import QUrl
from PyQt5.QtCore import pyqtSignal

from galacteek import log
from galacteek import logUser
from galacteek import ensure
from galacteek.dweb.enswhois import ensContentHash
from galacteek.ipfs.cidhelpers import IPFSPath

from yarl import URL


SCHEME_DWEB = 'dweb'
SCHEME_FS = 'fs'
SCHEME_IPFS = 'ipfs'
SCHEME_ENS = 'ens'


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

    schemeEns = QWebEngineUrlScheme(SCHEME_ENS.encode())
    schemeEns.setFlags(QWebEngineUrlScheme.SecureScheme)

    QWebEngineUrlScheme.registerScheme(schemeDweb)
    QWebEngineUrlScheme.registerScheme(schemeFs)
    QWebEngineUrlScheme.registerScheme(schemeIpfs)
    QWebEngineUrlScheme.registerScheme(schemeEns)


class ENSWhoisSchemeHandler(QWebEngineUrlSchemeHandler):
    contentReady = pyqtSignal(str, QWebEngineUrlRequestJob, str, bytes)
    domainResolved = pyqtSignal(str, IPFSPath)

    def __init__(self, app, parent=None):
        QWebEngineUrlSchemeHandler.__init__(self, parent)

        self.app = app
        self.requests = {}

    def onRequestDestroyed(self, uid):
        if uid in self.requests:
            del self.requests[uid]

    async def handleRequest(self, request):
        rUrl = request.requestUrl()
        if not rUrl.isValid():
            return

        domain = rUrl.host()
        uPath = rUrl.path()

        if not domain or len(domain) > 512:
            logUser.info('ENS: invalid domain request')
            return

        logUser.info('ENS: resolving {0}'.format(domain))

        path = await ensContentHash(domain)
        if path and path.valid:
            self.domainResolved.emit(domain, path)
            sPath = path.child(uPath) if uPath else path
            logUser.info('ENS: {domain} resolved to {res}'.format(
                domain=domain, res=sPath.dwebUrl))
            return request.redirect(QUrl(sPath.dwebUrl))
        else:
            logUser.info('ENS: {domain} resolve failed'.format(
                domain=domain))
            request.fail(QWebEngineUrlRequestJob.UrlInvalid)

    def requestStarted(self, request):
        uid = str(uuid.uuid4())
        self.requests[uid] = request
        request.destroyed.connect(lambda: self.onRequestDestroyed(uid))
        ensure(self.handleRequest(self.requests[uid]))


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
