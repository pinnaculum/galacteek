import re
import aioipfs
import functools
import asyncio
import aiodns
import async_timeout
import collections
import time
import traceback
import aiohttp
from yarl import URL
from datetime import datetime
from cachetools import TTLCache

from PyQt5.QtWebEngineCore import QWebEngineUrlSchemeHandler
from PyQt5.QtWebEngineCore import QWebEngineUrlScheme
from PyQt5.QtWebEngineCore import QWebEngineUrlRequestJob

from PyQt5.QtCore import QUrl
from PyQt5.QtCore import QIODevice
from PyQt5.QtCore import QBuffer
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QMutex

from galacteek import log
from galacteek import logUser
from galacteek import ensure
from galacteek import ensureSafe
from galacteek import database
from galacteek import AsyncSignal
from galacteek.ipfs import ipfsOp
from galacteek.ipfs.mimetype import detectMimeTypeFromBuffer
from galacteek.ipfs.mimetype import MIMEType
from galacteek.ipfs.cidhelpers import joinIpfs
from galacteek.ipfs.cidhelpers import joinIpns
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ipfs.cidhelpers import ipfsRegSearchCid32
from galacteek.ipfs.cidhelpers import domainValid
from galacteek.ipfs.ipfsops import APIErrorDecoder
from galacteek.dweb.render import renderTemplate
from galacteek.dweb.enswhois import ensContentHash
from galacteek.core.asynccache import cachedcoromethod
from galacteek.core import runningApp
from galacteek.config import cGet

from galacteek.ipdapps import dappsRegisterSchemes

from galacteek.qt.webengine import webEngine515


# Core schemes (the URL schemes your children will soon teach you how to use)
SCHEME_DWEB = 'dweb'
SCHEME_DWEBGW = 'dwebgw'
SCHEME_FS = 'fs'
SCHEME_IPFS = 'ipfs'
SCHEME_IPNS = 'ipns'
SCHEME_IPID = 'ipid'
SCHEME_IPS = 'ips'
SCHEME_I = 'inter'
SCHEME_QDAPP = 'qdapp'
SCHEME_GEMINI = 'gemini'
SCHEME_GEMIPFS = 'gemipfs'
SCHEME_GEMI = 'gemi'
SCHEME_GEM = 'gem'

# ENS-related schemes (ensr is redirect-on-resolve ENS scheme)
SCHEME_ENS = 'ens'
SCHEME_ENSR = 'ensr'
SCHEME_E = 'e'

# Obsolete schemes :)
SCHEME_HTTP = 'http'
SCHEME_HTTPS = 'https'
SCHEME_FTP = 'ftp'

# Misc schemes
SCHEME_Z = 'z'
SCHEME_Q = 'q'
SCHEME_QMAP = 'qmap'
SCHEME_GALACTEEK = 'glk'
SCHEME_PALACE = 'palace'
SCHEME_MANUAL = 'manual'

# Pronto schemes
SCHEME_PRONTO = 'pronto'
SCHEME_PRONTO_GRAPHS = 'prontog'

SCHEME_CHROMIUM = 'chromium'


# Default flags used by declareUrlScheme()

if webEngine515() is True:
    defaultSchemeFlags = QWebEngineUrlScheme.SecureScheme | \
        QWebEngineUrlScheme.ViewSourceAllowed | \
        QWebEngineUrlScheme.CorsEnabled
else:
    defaultSchemeFlags = QWebEngineUrlScheme.SecureScheme | \
        QWebEngineUrlScheme.ViewSourceAllowed


defaultLocalSchemeFlags = defaultSchemeFlags | QWebEngineUrlScheme.LocalScheme
serviceWorkersFlags = \
    defaultSchemeFlags | QWebEngineUrlScheme.ServiceWorkersAllowed


# Registered URL schemes
urlSchemes = {}


def allUrlSchemes():
    global urlSchemes
    return urlSchemes


def isSchemeRegistered(scheme):
    global urlSchemes
    for section, schemes in urlSchemes.items():
        if scheme in schemes:
            return True


def schemeSectionMatch(scheme, section):
    global urlSchemes
    schemes = urlSchemes.get(section, {})
    return scheme in schemes


def isUrlSupported(url):
    return isSchemeRegistered(url.scheme()) or url.scheme() in [
        SCHEME_HTTP,
        SCHEME_HTTPS,
        SCHEME_FTP,
        SCHEME_CHROMIUM
    ]


def declareUrlScheme(name,
                     flags=defaultSchemeFlags,
                     syntax=QWebEngineUrlScheme.Syntax.Host,
                     defaultPort=QWebEngineUrlScheme.PortUnspecified,
                     schemeSection='core'):
    global urlSchemes
    scheme = QWebEngineUrlScheme(name.encode())
    scheme.setFlags(flags)
    scheme.setSyntax(syntax)
    scheme.setDefaultPort(defaultPort)
    QWebEngineUrlScheme.registerScheme(scheme)
    urlSchemes.setdefault(schemeSection, {})
    urlSchemes[schemeSection][name] = scheme
    return scheme


def enableSchemeFlag(name: str, flag):
    scheme = QWebEngineUrlScheme.schemeByName(name.encode())
    if scheme:
        scheme.setFlags(scheme.flags() | flag)


def registerMiscSchemes():
    declareUrlScheme(SCHEME_MANUAL,
                     syntax=QWebEngineUrlScheme.Syntax.Path,
                     schemeSection='misc'
                     )
    declareUrlScheme(SCHEME_Z,
                     syntax=QWebEngineUrlScheme.Syntax.Path,
                     flags=QWebEngineUrlScheme.LocalScheme,
                     schemeSection='misc'
                     )
    declareUrlScheme(SCHEME_GALACTEEK,
                     syntax=QWebEngineUrlScheme.Syntax.Path,
                     flags=QWebEngineUrlScheme.LocalScheme,
                     schemeSection='core'
                     )
    declareUrlScheme(SCHEME_QMAP,
                     syntax=QWebEngineUrlScheme.Syntax.Host,
                     flags=QWebEngineUrlScheme.LocalScheme,
                     schemeSection='core'
                     )


def initializeSchemes():
    name = QWebEngineUrlScheme.schemeByName(SCHEME_DWEB.encode()).name()
    if name:
        log.debug('initializeSchemes() already called')
        return

    declareUrlScheme(
        SCHEME_DWEB,
        syntax=QWebEngineUrlScheme.Syntax.Path,
        flags=serviceWorkersFlags
    )

    declareUrlScheme(
        SCHEME_DWEBGW,
        syntax=QWebEngineUrlScheme.Syntax.Path,
        flags=serviceWorkersFlags
    )

    declareUrlScheme(
        SCHEME_FS,
        syntax=QWebEngineUrlScheme.Syntax.Path,
        flags=serviceWorkersFlags
    )

    declareUrlScheme(
        SCHEME_IPFS,
        syntax=QWebEngineUrlScheme.Syntax.Host,
        flags=serviceWorkersFlags
    )

    declareUrlScheme(
        SCHEME_IPNS,
        syntax=QWebEngineUrlScheme.Syntax.Host,
        flags=serviceWorkersFlags
    )

    declareUrlScheme(
        SCHEME_IPID,
        syntax=QWebEngineUrlScheme.Syntax.Host,
        flags=defaultSchemeFlags |
        QWebEngineUrlScheme.ContentSecurityPolicyIgnored
    )

    declareUrlScheme(
        SCHEME_I,
        syntax=QWebEngineUrlScheme.Syntax.Path,
        flags=defaultSchemeFlags
    )

    declareUrlScheme(
        SCHEME_ENS,
        syntax=QWebEngineUrlScheme.Syntax.Host,
        flags=serviceWorkersFlags
    )

    declareUrlScheme(
        SCHEME_ENSR,
        syntax=QWebEngineUrlScheme.Syntax.Host
    )

    declareUrlScheme(
        SCHEME_GEMINI,
        syntax=QWebEngineUrlScheme.Syntax.Host,
        flags=defaultSchemeFlags
    )

    declareUrlScheme(
        SCHEME_GEMI,
        syntax=QWebEngineUrlScheme.Syntax.Path,
        flags=defaultSchemeFlags
    )

    declareUrlScheme(
        SCHEME_GEM,
        syntax=QWebEngineUrlScheme.Syntax.Host,
        flags=defaultSchemeFlags
    )

    declareUrlScheme(
        SCHEME_PRONTO_GRAPHS,
        syntax=QWebEngineUrlScheme.Syntax.Path
    )

    dappsRegisterSchemes()

    registerMiscSchemes()


def isIpfsUrl(url):
    if url.isValid():
        return url.scheme() in [SCHEME_FS, SCHEME_DWEB, SCHEME_DWEBGW,
                                SCHEME_IPFS, SCHEME_IPNS]


def isNativeIpfsUrl(url):
    if url.isValid():
        return url.scheme() in [SCHEME_IPFS, SCHEME_IPNS]


def isEnsUrl(url):
    if url.isValid():
        return url.scheme() in [SCHEME_ENS, SCHEME_ENSR]


def isHttpUrl(url):
    if url.isValid():
        return url.scheme() in [SCHEME_HTTP, SCHEME_HTTPS]


def isGeminiUrl(url):
    if url.isValid():
        return url.scheme() == SCHEME_GEMINI


class BaseURLSchemeHandler(QWebEngineUrlSchemeHandler):
    webProfileNeeded = None
    psListener = None
    psListenerClass = None

    def __init__(self, parent=None, noMutexes=False):
        super(BaseURLSchemeHandler, self).__init__(parent)

        self.requests = {}
        self.noMutexes = noMutexes
        self.app = runningApp()

        if self.psListenerClass:
            # can't instantiate this before the hub is created ..
            self.psListener = self.psListenerClass()

    def reqFailedCall(self, request, code):
        try:
            return request.fail(code)
        except RuntimeError:
            # wrapped C/C++ object deleted ?
            pass
        except Exception:
            pass

    def reqFailed(self, request):
        return self.reqFailedCall(
            request, QWebEngineUrlRequestJob.RequestFailed)

    def urlInvalid(self, request):
        return self.reqFailedCall(
            request, QWebEngineUrlRequestJob.UrlInvalid)

    def urlNotFound(self, request):
        return self.reqFailedCall(
            request, QWebEngineUrlRequestJob.UrlNotFound)

    def aborted(self, request):
        return self.reqFailedCall(
            request, QWebEngineUrlRequestJob.RequestAborted)

    def allocReqId(self, req):
        # TS is good enough
        uid = str(time.time())

        while uid in self.requests:
            uid = str(time.time())

        self.requests[uid] = {
            'request': req,
            'iodev': QBuffer(parent=req),
            'mutex': QMutex() if not self.noMutexes else None
        }

        return uid

    async def handleRequest(self, request, uid):
        return self.urlInvalid(request)

    async def delegateToThread(self, awaitable):
        raise Exception('Not implemented')

    def onRequestDestroyed(self, uid):
        if uid in self.requests:
            del self.requests[uid]

    def requestStarted(self, request):
        uid = self.allocReqId(request)
        request.reqUid = uid
        request.destroyed.connect(
            functools.partial(self.onRequestDestroyed, uid))
        ensureSafe(self.handleRequest(request, uid))

    async def serveTemplate(self,
                            request,
                            tmplName,
                            **kwargs):
        tmpl = await renderTemplate(
            tmplName,
            **kwargs
        )
        if tmpl:
            self.serveContent(
                request.reqUid,
                request,
                'text/html',
                tmpl.encode()
            )

    def serveContent(self, uid, request, ctype, data):
        if uid not in self.requests:
            # Destroyed ?
            return

        mutex = self.requests[uid]['mutex']

        if mutex and not self.noMutexes:
            mutex.lock()

        try:
            buf = self.requests[uid]['iodev']
            buf.open(QIODevice.WriteOnly)
            buf.write(data)
            buf.close()

            request.reply(ctype.encode('ascii'), buf)

            # Should disabled based on config for the scheme
            # self.objectServed.emit(ipfsPath, ctype, time.time())

            if mutex and not self.noMutexes:
                mutex.unlock()
        except Exception:
            if mutex and not self.noMutexes:
                mutex.unlock()

            log.debug('Error buffering request data')
            request.fail(QWebEngineUrlRequestJob.RequestFailed)


class IPFSObjectProxyScheme:
    """
    For schemes that proxy/map IPFS objects
    """

    async def urlProxiedPath(self, url):
        """
        Return the object mapped for `url`
        """
        raise Exception('Implement urlProxiedPath()')


# Aync signal fired when an ENS domain was resolved
ensDomainResolved = AsyncSignal(str, IPFSPath)


class ENSWhoisSchemeHandler(BaseURLSchemeHandler):
    """
    Deprecated ENS resolver (that was using api.whoisens.org)
    """

    contentReady = pyqtSignal(str, QWebEngineUrlRequestJob, str, bytes)

    def __init__(self, app, parent=None):
        super(ENSWhoisSchemeHandler, self).__init__(parent)

        self.app = app
        self.requests = {}

    async def handleRequest(self, request):
        rUrl = request.requestUrl()
        if not rUrl.isValid():
            return self.urlInvalid(request)

        domain = rUrl.host()
        uPath = rUrl.path()

        if not domain or len(domain) > 512:
            logUser.info('ENS: invalid domain request')
            return self.urlInvalid(request)

        logUser.info('ENS: resolving {0}'.format(domain))

        path = await ensContentHash(domain, sslverify=self.app.sslverify)
        if path and path.valid:
            await ensDomainResolved.emit(domain, path)
            sPath = path.child(uPath) if uPath else path
            logUser.info('ENS: {domain} resolved to {res}'.format(
                domain=domain, res=sPath.ipfsUrl))
            return request.redirect(QUrl(sPath.ipfsUrl))
        else:
            logUser.info('ENS: {domain} resolve failed'.format(
                domain=domain))
            request.fail(QWebEngineUrlRequestJob.UrlInvalid)


class EthDNSError(Exception):
    pass


class EthDNSResolver:
    def __init__(self, loop, verify_ssl=True):
        self.dnsResolver = aiodns.DNSResolver(loop=loop)
        self.verify_ssl = verify_ssl

    def debug(self, msg):
        log.debug('EthDNS resolver: {}'.format(msg))

    @cachedcoromethod(TTLCache(128, 120))
    async def _resolve_old(self, domain):
        """
        Deprecated
        EthDNS uses the .link TLD
        domainWLink = '{domain}.link'.format(domain=domain)
        """

        result = await self.dnsResolver.query(domain, 'TXT')

        if not result:
            self.debug('Failed to resolve {}'.format(domain))
            return None

        for entry in result:
            # Grab the dnslink

            match = re.search('^dnslink=(.*)$', entry.text)
            if not match:
                continue

            return match.group(1)

    @cachedcoromethod(TTLCache(128, 180))
    async def _resolve(self, domain):
        """
        TTL-cached EthDNS resolver

        This uses the DNS-over-HTTPS eth.link JSON API
        """

        url = 'https://eth.link/dns-query'
        dnsJsonCtype = 'application/dns-json'
        headers = {'content-type': dnsJsonCtype}
        reply = None

        try:
            async with aiohttp.ClientSession(headers=headers) as sess:
                async with sess.get(url,
                                    verify_ssl=self.verify_ssl,
                                    params={
                                        'type': 'TXT',
                                        'name': domain
                                    }) as resp:
                    reply = await resp.json(
                        content_type=dnsJsonCtype
                    )
        except Exception as e:
            raise EthDNSError(
                f'Could not resolve eth domain: {domain}: {e}')

        if reply:
            try:
                for ans in reply['Answer']:
                    if 'data' not in ans:
                        continue

                    match = re.search('^\"*?dnslink=(.*?)\"*?$', ans['data'])
                    if not match:
                        continue

                    return match.group(1).lstrip()

                raise EthDNSError(
                    f'Could not resolve eth domain: {domain}: '
                    'No dnslink found'
                )
            except Exception as e:
                raise EthDNSError(
                    f'Could not resolve eth domain: {domain}: {e}')
        else:
            raise EthDNSError(
                f'Could not resolve eth domain: {domain}: Empty reply')

    async def resolveEnsDomain(self, domain, timeout=20):
        """
        Resolve an ENS domain with EthDNS, and return the
        IPFS path for this domain

        :param str domain: Eth domain name to resolve (e.g mydomain.eth)
        :rtype: IPFSPath
        """

        try:
            with async_timeout.timeout(timeout):
                return await self._resolve(domain)
        except asyncio.TimeoutError:
            self.debug('Timeout resolving domain {}'.format(domain))
        except Exception as err:
            self.debug('Error while resolving domain {0}: {1}'.format(
                domain, str(err)))


class EthDNSSchemeHandler(BaseURLSchemeHandler):
    """
    ENS scheme handler (resolves ENS domains through EthDNS with aiodns)

    Redirects to the resolved IPFS object
    """

    contentReady = pyqtSignal(str, QWebEngineUrlRequestJob, str, bytes)

    def __init__(self, app, resolver=None, parent=None):
        super(EthDNSSchemeHandler, self).__init__(parent=parent)

        self.app = app
        self.ethResolver = resolver if resolver else \
            EthDNSResolver(self.app.loop, verify_ssl=self.app.sslverify)

    def debug(self, msg):
        log.debug('EthDNS: {}'.format(msg))

    async def handleRequest(self, request):
        rUrl = request.requestUrl()
        if not rUrl.isValid():
            return self.urlInvalid(request)

        domain = rUrl.host()
        uPath = rUrl.path()

        if not domain or len(domain) > 512 or not domainValid(domain):
            log.info('EthDNS: invalid domain request')
            return self.urlInvalid(request)

        pathRaw = await self.ethResolver.resolveEnsDomain(domain)
        path = IPFSPath(pathRaw, autoCidConv=True)

        if path and path.valid:
            await ensDomainResolved.emit(domain, path)

            sPath = path.child(uPath) if uPath else path
            log.debug('EthDNS: {domain} resolved to {res}'.format(
                domain=domain, res=sPath.ipfsUrl))
            return request.redirect(QUrl(sPath.dwebUrl))
        else:
            log.info('EthDNS: {domain} resolve failed'.format(
                domain=domain))
            return self.urlNotFound(request)


class NativeIPFSSchemeHandler(BaseURLSchemeHandler):
    """
    Native scheme handler for URLs using the ipfs://<cidv1base32>
    or ipns://<fqdn>/.. formats

    We don't use the gateway at all here, making the async requests
    manually on the daemon.

    The requestStarted() function will first assign a UUID to the
    request and store the request in the handler so that it doesn't get
    garbage-collected by QtWebEngine. The handleRequest() coroutine
    is responsible for fetching the objects from IPFS. When the data
    is ready it will call the renderData() coroutine which will detect
    the MIME type, and emit the 'contentReady' signal which is handled
    by the 'serveContent' callback.
    """

    # contentReady signal (handled by onContent())
    # Unused now
    contentReady = pyqtSignal(
        str, QWebEngineUrlRequestJob, IPFSPath, str, bytes)

    # objectServed signal: emitted when an object has been fetched and
    # served to a QtWebEngine request
    objectServed = pyqtSignal(IPFSPath, str, float)

    def __init__(self, app, parent=None, validCidQSize=32,
                 noMutexes=True):
        super(NativeIPFSSchemeHandler, self).__init__(
            parent=parent,
            noMutexes=noMutexes)

        self.app = app
        self.validCids = collections.deque([], validCidQSize)

        self.requestTimeout = cGet('schemes.ipfsNative.reqTimeout')

    def debug(self, msg):
        log.debug(f'Native scheme handler (DEBUG): {msg}')

    def warning(self, msg):
        log.warning(f'Native scheme handler (WARNING): {msg}')

    def info(self, msg):
        log.warning(f'Native scheme handler (INFO): {msg}')

    async def directoryListing(self, request, ipfsop, path):
        currentIpfsPath = IPFSPath(path)

        if not currentIpfsPath.valid:
            self.debug('Invalid path: {0}'.format(path))
            return

        ctx = {}
        try:
            listing = await ipfsop.listObject(path)
        except aioipfs.APIError:
            self.debug('Error listing directory for path: {0}'.format(path))
            return None

        if 'Objects' not in listing:
            return None

        ctx['path'] = path
        ctx['links'] = []

        if len(listing['Objects']) > 0:
            obj = listing['Objects'].pop()
            ctx['links'] += obj.get('Links', [])

        for lnk in ctx['links']:
            lType = lnk.get('Type')

            if lType == 1:
                lnk['href'] = lnk['Name'] + '/'
            else:
                lnk['href'] = lnk['Name']

        try:
            data = await renderTemplate('ipfsdirlisting.html', **ctx)
        except:
            self.debug('Failed to render directory listing template')
        else:
            return data.encode()

    async def renderDirectory(self, request, ipfsop, path):
        ipfsPath = IPFSPath(path)
        indexPath = ipfsPath.child('index.html')

        try:
            data = await ipfsop.catObject(str(indexPath))
        except aioipfs.APIError as exc:
            dec = APIErrorDecoder(exc)

            if dec.errNoSuchLink():
                return await self.directoryListing(
                    request, ipfsop, path)

            return self.urlInvalid(request)
        else:
            return data

    async def renderDagListing(self, request, client, path, **kw):
        return b'ENOTIMPLEMENTED'

    async def renderDagNode(self, request, uid, ipfsop, ipfsPath, **kw):
        self.debug('DAG node render: {}'.format(ipfsPath))
        indexPath = ipfsPath.child('index.html')

        try:
            stat = None
            try:
                with async_timeout.timeout(20):
                    stat = await ipfsop.client.object.stat(str(indexPath))
            except asyncio.TimeoutError:
                return self.urlInvalid(request)
            except Exception:
                return self.reqFailed(request)

            if not stat:
                return await self.renderDagListing(request,
                                                   ipfsop.client, ipfsPath,
                                                   **kw)
            else:
                # The index is present, redirect
                urlR = QUrl(indexPath.ipfsUrl)

                if urlR.isValid():
                    request.redirect(urlR)
        except aioipfs.APIError:
            return await self.renderDagListing(
                request, ipfsop.client, ipfsPath, **kw)

    async def renderDataEmit(self, request, ipfsPath, data, uid):
        cType = await detectMimeTypeFromBuffer(data[0:512])

        if cType:
            self.contentReady.emit(
                uid, request, ipfsPath, cType.type, data)
        else:
            self.debug('Impossible to detect MIME type for URL: {0}'.format(
                request.requestUrl().toString()))
            self.contentReady.emit(
                uid, request, 'application/octet-stream', data)

    async def renderData(self, request, ipfsPath, data, uid):
        cType = await detectMimeTypeFromBuffer(data[0:512])

        if cType and cType.isText:
            if ipfsPath.objPath.endswith('.css'):
                # Should add CSS rules in libmagic
                # QtWebEngine really wants 'text/css'
                cType = MIMEType('text/css')

        if cType:
            self.serveContent(
                uid, request, cType.type, data)
        else:
            self.debug('Impossible to detect MIME type for URL: {0}'.format(
                request.requestUrl().toString()))
            self.serveContent(
                uid, request, 'application/octet-stream', data)

    @ipfsOp
    async def handleRequest(self, ipfsop, request, uid):
        rUrl = request.requestUrl()
        scheme = rUrl.scheme()
        host = rUrl.host()

        if not host:
            return self.urlInvalid(request)

        if scheme == SCHEME_IPFS:
            # hostname = base32-encoded CID or FQDN
            #
            # We keep a list (deque) of CIDs that have been validated.
            # If you hit a page which references a lot of other resources
            # for instance, this should be faster than regexp

            if domainValid(host):
                ipfsPathS = joinIpns(host) + rUrl.path()
            else:
                if host not in self.validCids:
                    if not ipfsRegSearchCid32(host):
                        return self.urlInvalid(request)

                    self.validCids.append(host)

                ipfsPathS = joinIpfs(host) + rUrl.path()
        elif scheme == SCHEME_IPNS:
            ipfsPathS = joinIpns(host) + rUrl.path()
        else:
            return self.urlInvalid(request)

        ipfsPath = IPFSPath(ipfsPathS)
        if not ipfsPath.valid:
            return self.urlInvalid(request)

        try:
            with async_timeout.timeout(self.requestTimeout):
                return await self.fetchFromPath(ipfsop, request, ipfsPath, uid)
        except asyncio.TimeoutError:
            return self.reqFailed(request)
        except Exception as err:
            # Any other error

            traceback.print_exc()
            self.debug(f'Unknown error while serving request: {err}')

            return self.reqFailed(request)

    async def fetchFromPath(self, ipfsop, request, ipfsPath, uid, **kw):
        try:
            data = await ipfsop.catObject(ipfsPath.objPath)
        except aioipfs.APIError as exc:
            await asyncio.sleep(0)

            self.info('API error ({path}): {err}'.format(
                path=str(ipfsPath), err=exc.message)
            )

            dec = APIErrorDecoder(exc)

            if dec.errNoSuchLink():
                return self.urlNotFound(request)

            if dec.errIsDirectory():
                data = await self.renderDirectory(
                    request,
                    ipfsop,
                    str(ipfsPath)
                )
                if data:
                    return await self.renderData(request, ipfsPath, data, uid)

            if dec.errUnknownNode():
                # DAG / TODO
                data = await self.renderDagNode(
                    request,
                    uid,
                    ipfsop,
                    ipfsPath
                )
                if data:
                    return await self.renderData(request, ipfsPath, data, uid)
        except Exception as gerr:
            log.debug(f'fetchFromPath, unknown error: {gerr}')
            return None
        else:
            if data:
                return await self.renderData(request, ipfsPath, data, uid)


class ObjectProxySchemeHandler(NativeIPFSSchemeHandler, IPFSObjectProxyScheme):
    """
    This scheme handler acts as a "proxy" to an IPFS path.

    For example, by mapping the url scheme 'docs' to this path:

    /ipfs/bafybeihw6pfoai7wbyt5jhbiialicees3vn336fkrdmjlbheh2dqsxsmlu/

    Accessing 'docs:/pdf/today.pdf' will access the IPFS object at

    /ipfs/bafybeihw6pfoai7wbyt5jhbiialicees3vn336fkrdmjlbheh2dqsxsmlu/pdf/today.pdf
    """

    def __init__(self, app, ipfsPath, parent=None):
        """
        :param IPFSPath ipfsPath: the path to proxy to
        """
        super(ObjectProxySchemeHandler, self).__init__(app, parent=parent)

        self.proxiedPath = ipfsPath

    async def urlProxiedPath(self, url):
        return self.proxiedPath.child(url.path())

    @ipfsOp
    async def handleRequest(self, ipfsop, request, uid):
        if not self.proxiedPath.valid:
            return request.fail(QWebEngineUrlRequestJob.UrlInvalid)

        rUrl = request.requestUrl()
        ipfsPath = await self.urlProxiedPath(rUrl)

        if not ipfsPath or not ipfsPath.valid:
            return self.urlInvalid(request)

        return await self.fetchFromPath(ipfsop, request, ipfsPath, uid)


class MultiObjectHostSchemeHandler(NativeIPFSSchemeHandler,
                                   IPFSObjectProxyScheme):
    """
    Somehow similar to ObjectProxySchemeHandler, but this handler
    is host-based, the host being the name of a user-defined
    name-to-ipfs-path mapping. Used by the qmap:// scheme.
    A URL would look like this (with foo being the mapping name)::

        qmap://foo/src/luser.c

    If the mapped object is an IPNS path, it's periodically
    resolved and the result is cached.
    """

    def __init__(self, app, parent=None):
        super(MultiObjectHostSchemeHandler, self).__init__(app, parent=parent)

        self.app.towers['schemes'].qMappingsChanged.connectTo(
            self.onMappingsChanged)

        self.lock = asyncio.Lock()
        self.mappings = {}
        self._resolverTask = None

    async def urlProxiedPath(self, rUrl):
        host = rUrl.host()

        if host not in self.mappings:
            return None

        mapping = self.mappings[host]
        rCached = mapping['rcache']
        mappedTo = mapping['path']

        usedPath = rCached if rCached and rCached.valid else mappedTo

        if not usedPath.valid:
            return None

        path = rUrl.path()
        ipfsPath = usedPath.child(path)
        return ipfsPath

    async def onMappingsChanged(self):
        await self.updateMappings()

    async def updateMappings(self):
        mappings = await database.hashmarkMappingsAll()
        for mapping in mappings:
            if mapping.name in self.mappings:
                continue

            await mapping.fetch_related('qahashmark')

            async with self.lock:
                self.mappings[mapping.name] = {
                    'path': IPFSPath(mapping.qahashmark.path),
                    'rfrequency': mapping.ipnsresolvefreq,
                    'rcache': None,
                    'rlast': None
                }

    async def start(self, **kw):
        if not self._resolverTask:
            self._resolverTask = ensure(self.mappingsResolver())

        await self.updateMappings()

    @ipfsOp
    async def mappingsResolver(self, ipfsop):
        while True:
            async with self.lock:
                for name, m in self.mappings.items():
                    now = datetime.now()
                    path = m['path']

                    if not path.isIpns:
                        continue

                    if not m['rlast'] or \
                            (now - m['rlast']).seconds > m['rfrequency']:
                        resolved = await path.resolve(ipfsop, noCache=True)
                        if resolved:
                            m['rcache'] = IPFSPath(resolved)
                            m['rlast'] = now

            await asyncio.sleep(60)

    @ipfsOp
    async def handleRequest(self, ipfsop, request, uid):
        rUrl = request.requestUrl()

        if not rUrl.host():
            return self.urlInvalid(request)

        ipfsPath = await self.urlProxiedPath(rUrl)

        if not ipfsPath or not ipfsPath.valid:
            return self.urlInvalid(request)

        return await self.fetchFromPath(ipfsop, request, ipfsPath, uid)


class DAGProxySchemeHandler(NativeIPFSSchemeHandler):
    """
    This scheme handler acts as a "proxy" to a DAG
    """

    def __init__(self, app, parent=None):
        super(DAGProxySchemeHandler, self).__init__(app, parent=parent)

        # The DAG being proxied
        self.proxied = None

    async def getDag(self):
        raise Exception('implement getDag()')

    async def renderDagListing(self, request, client, path):
        listing = await self.proxied.list(
            path=path.subPath if path.subPath else '')
        if not listing:
            return b'ELISTING'

        ctx = {}
        ctx['path'] = str(path)
        ctx['links'] = []

        for nname in listing:
            child = path.child(nname)
            ctx['links'].append({
                'name': nname,
                'href': child.ipfsUrl
            })

        try:
            data = await renderTemplate('ipfsdagnodelisting.html', **ctx)
        except:
            pass
        else:
            return data.encode()

    async def renderDagNode(self, request, uid, ipfsop, ipfsPath, **kw):
        self.debug('DAG node render: {}'.format(ipfsPath))

        indexPath = ipfsPath.child('index.html')

        try:
            stat = None
            try:
                with async_timeout.timeout(20):
                    stat = await ipfsop.client.object.stat(str(indexPath))
            except asyncio.TimeoutError:
                return self.urlInvalid(request)
            except Exception:
                return self.reqFailed(request)

            if not stat:
                return await self.renderDagListing(
                    request, ipfsop.client, ipfsPath, **kw)
            else:
                # The index is present, fetch it
                return await self.fetchFromPath(
                    ipfsop, request, indexPath, uid)
        except aioipfs.APIError:
            return await self.renderDagListing(
                request, ipfsop.client, ipfsPath, **kw)

    @ipfsOp
    async def handleRequest(self, ipfsop, request, uid):
        if self.proxied is None:
            self.proxied = await self.getDag()

        if not self.proxied:
            return request.fail(QWebEngineUrlRequestJob.UrlInvalid)

        rUrl = request.requestUrl()
        path = rUrl.path()
        ipfsPathS = joinIpfs(self.proxied.dagCid) + path

        log.debug(f'Proxying from DAG {self.proxied}: {ipfsPathS}')

        ipfsPath = IPFSPath(ipfsPathS)
        if not ipfsPath.valid:
            return self.urlInvalid(request)

        return await self.fetchFromPath(ipfsop, request, ipfsPath, uid)


class DAGWatchSchemeHandler(DAGProxySchemeHandler):
    def __init__(self, app, dappName, parent=None):
        super(DAGWatchSchemeHandler, self).__init__(app, parent=parent)

        self.name = dappName
        self.app.towers['dags'].dappDeployedAtCid.connect(self.onDappDeployed)

    def onDappDeployed(self, dag, name, cid):
        if name == self.name:
            self.proxied = dag

    @ipfsOp
    async def getDag(self, ipfsop):
        return self.proxied


class DWebSchemeHandlerNative(NativeIPFSSchemeHandler):
    """
    IPFS dweb scheme handler, supporting URLs such as:

        dweb:/ipfs/multihash
        dweb:/ipns/domain.com/path
        dweb://ipfs/multihash/...
        fs:/ipfs/multihash
        etc..
    """

    @ipfsOp
    async def handleRequest(self, ipfsop, request, uid):
        rUrl = request.requestUrl()

        ipfsPath = IPFSPath(rUrl.toString())

        if not ipfsPath.valid:
            return self.urlInvalid(request)

        try:
            with async_timeout.timeout(self.requestTimeout):
                return await self.fetchFromPath(ipfsop, request, ipfsPath, uid)
        except asyncio.TimeoutError:
            return self.reqFailed(request)
        except Exception as err:
            # Any other error
            self.debug(str(err))
            return self.reqFailed(request)


class DWebSchemeHandlerGateway(BaseURLSchemeHandler):
    """
    IPFS dweb scheme handler, supporting URLs such as:

        dweb:/ipfs/multihash
        dweb:/ipns/domain.com/path
        dweb://ipfs/multihash/...
        fs:/ipfs/multihash
        etc..

    Uses redirects to the IPFS HTTP gateway
    """

    def __init__(self, app, parent=None):
        super(DWebSchemeHandlerGateway, self).__init__(parent)
        self.app = app

    def redirectIpfs(self, request, path, url):
        yUrl = URL(url.toString())

        if len(yUrl.parts) < 3:
            return self.urlInvalid(request)

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

        if scheme in [SCHEME_FS, SCHEME_DWEB, SCHEME_DWEBGW]:
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
            self.urlInvalid(request)
            return

        path = url.path()
        if not isinstance(path, str):
            self.urlInvalid(request)
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


class MultiDAGProxySchemeHandler(NativeIPFSSchemeHandler):
    """
    Proxy handler to a stack of DAGs (first DAG registered is the
    first DAG tried).
    """

    def __init__(self, app, parent=None):
        super(MultiDAGProxySchemeHandler, self).__init__(app, parent=parent)
        self.proxied = []

    def useDag(self, dag):
        self.proxied.append(dag)

    async def renderDagListing(self, request, client, path, **kw):
        dag = kw.pop('dag', None)
        assert dag is not None

        listing = await dag.list(
            path=path.subPath if path.subPath else '')
        if not listing:
            return b'ELISTING'

        ctx = {}
        ctx['path'] = str(path)
        ctx['links'] = []

        for nname in listing:
            child = path.child(nname)
            ctx['links'].append({
                'name': nname,
                'href': child.ipfsUrl
            })

        try:
            data = await renderTemplate('ipfsdagnodelisting.html', **ctx)
        except:
            pass
        else:
            return data.encode()

    @ipfsOp
    async def handleRequest(self, ipfsop, request, uid):
        if len(self.proxied) == 0:
            return self.urlInvalid(request)

        rUrl = request.requestUrl()
        path = rUrl.path()

        for dag in self.proxied:
            if not dag.dagCid:
                continue

            ipfsPathS = joinIpfs(dag.dagCid) + path
            ipfsPath = IPFSPath(ipfsPathS)

            if not ipfsPath.valid:
                return request.fail(QWebEngineUrlRequestJob.UrlInvalid)

            return await self.fetchFromPath(ipfsop, request, ipfsPath, uid,
                                            dag=dag)

    async def fetchFromPath(self, ipfsop, request, ipfsPath, uid, **kw):
        dag = kw.pop('dag', None)
        assert dag is not None

        log.debug('Multi DAG proxy : Fetch-from-path {}'.format(ipfsPath))
        try:
            data = await ipfsop.catObject(ipfsPath.objPath)
        except aioipfs.APIError as exc:
            await asyncio.sleep(0)

            self.debug('API error ({path}): {err}'.format(
                path=str(ipfsPath), err=exc.message)
            )

            dec = APIErrorDecoder(exc)

            if dec.errNoSuchLink():
                return self.urlNotFound(request)

            if dec.errIsDirectory():
                data = await self.renderDirectory(
                    request,
                    ipfsop,
                    str(ipfsPath)
                )
                if data:
                    return await self.renderData(request, ipfsPath, data, uid)

            if dec.errUnknownNode():
                # UNK DAG / TODO
                data = await self.renderDagNode(
                    request,
                    uid,
                    ipfsop,
                    ipfsPath,
                    dag=dag
                )
                if data:
                    return await self.renderData(request, ipfsPath, data, uid)
        else:
            return await self.renderData(request, ipfsPath, data, uid)


class EthDNSProxySchemeHandler(NativeIPFSSchemeHandler, IPFSObjectProxyScheme):
    """
    ENS scheme handler (resolves ENS domains through EthDNS with aiodns)

    This does not redirect to the IPFS object, but rather acts as a proxy.
    """

    def __init__(self, app, resolver=None, parent=None):
        super(EthDNSProxySchemeHandler, self).__init__(app, parent)

        self.ethResolver = resolver if resolver else \
            EthDNSResolver(self.app.loop, verify_ssl=self.app.sslverify)

    def debug(self, msg):
        log.debug('EthDNS proxy: {}'.format(msg))

    async def urlProxiedPath(self, rUrl):
        domain = rUrl.host()
        uPath = rUrl.path()

        if not domain or len(domain) > 512 or not domainValid(domain):
            return None

        pathRaw = await self.ethResolver.resolveEnsDomain(domain)
        path = IPFSPath(pathRaw, autoCidConv=True)

        if path and path.valid:
            return path.child(uPath) if uPath else path

    @ipfsOp
    async def handleRequest(self, ipfsop, request, uid):
        rUrl = request.requestUrl()
        domain = rUrl.host()

        if not domain or len(domain) > 512 or not domainValid(domain):
            logUser.info('EthDNS: invalid domain request')
            return self.urlInvalid(request)

        path = await self.urlProxiedPath(rUrl)

        if path and path.valid:
            return await self.fetchFromPath(ipfsop, request, path, uid)
        else:
            logUser.info('EthDNS: {domain} resolve failed'.format(
                domain=domain))
            return self.urlNotFound(request)
