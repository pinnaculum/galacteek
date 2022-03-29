import secrets
import json
import orjson
import attr
import zlib
import collections

from cachetools import TTLCache

from asyncio_throttle import Throttler

from aiohttp import web
from aiohttp import BasicAuth
from aiohttp import hdrs
from aiohttp_basicauth import BasicAuthMiddleware

from rdflib.plugins.sparql.parser import parseQuery
from rdflib_jsonld.serializer import resource_from_rdf

from galacteek import log
from galacteek.core import runningApp
from galacteek.core.asynclib import loopTime
from galacteek.ipfs.tunnel import P2PListener
from galacteek.ipfs.p2pservices import P2PService
from galacteek.ld.rdf import BaseGraph


MIME_N3 = 'text/rdf+n3'
MIME_TTL = 'text/turtle'
MIME_NTRIPLES = 'text/plain'

MIME_RESULTS_JSON = 'application/sparql-results+json'
MIME_RESULTS_XML = 'application/sparql-results+xml'
MIME_XTTL = 'application/x-turtle'
MIME_RDFXML = 'application/rdf+xml'
MIME_JSONLD = 'application/ld+json'


@attr.s(auto_attribs=True)
class SparQLServiceConfig:
    uri: str = ''
    exportsAllow: bool = False
    exportFormats: list = ['ttl', 'xml']


class SparQLWebApp(web.Application):
    pass


class SparQLSiteHandler:
    """
    SparQL HTTP service coroutines
    """

    def __init__(self, service):
        self.throttler = Throttler(
            rate_limit=500.0,
            period=30.0,
            retry_interval=2.0
        )
        self.service = service
        self.app = runningApp()

    @property
    def cfg(self):
        return self.service.config

    async def msgError(self, error='Invalid request', status=500):
        return web.json_response({
            'error': error
        }, status=status)

    async def peerAuthorized(self, request, auth: BasicAuth, loopTime: float):
        # TODO: filter based on peer activity
        return True

    async def resource(self, request):
        """
        Render the graph of a given resource
        """

        accepthl = request.headers.get(
            'Accept',
            MIME_TTL
        ).split(',')

        subject = request.match_info['rsc']

        context_data = request.query.get('context')
        compress = request.query.get('compress', 'gzip')
        # fmt = request.query.get('fmt', 'xml')

        if not isinstance(context_data, str):
            return await self.msgError(error='Invalid format')

        async with self.throttler:
            try:
                rsc = self.service.graph.resource(subject)
                assert rsc is not None

                graph = rsc.graph

                base = 'ips://galacteek.ld/'
                use_native_types = False
                use_rdf_type = False
                auto_compact = False

                obj = resource_from_rdf(rsc, context_data, base,
                                        use_native_types, use_rdf_type,
                                        auto_compact=auto_compact)
                graph = BaseGraph().parse(
                    data=json.dumps(obj), format='json-ld'
                )

                if MIME_TTL in accepthl or MIME_XTTL in accepthl:
                    data = await graph.ttlize()

                    ctype = MIME_TTL
                else:
                    return await self.msgError(error='Invalid format')

                if compress == 'gzip':
                    ctype = 'application/gzip'

                    return web.Response(
                        content_type=ctype,
                        body=zlib.compress(data)
                    )
                else:
                    return web.Response(
                        content_type=ctype,
                        text=data.decode()
                    )
            except Exception as err:
                log.debug(
                    f'{subject}: Could not render graph: {err}')
                return await self.msgError(error='Export error')

    async def export(self, request):
        """
        Export the graph in ttl/xml, via a GET method
        """

        if not self.service.config.exportsAllow:
            return await self.msgError(status=403)

        fmt = request.query.get('fmt', 'xml')
        compress = request.query.get('compress', 'gzip')

        graph = self.service.graph

        async with self.throttler:
            try:
                if fmt == 'xml':
                    data = await graph.xmlize()
                    ctype = 'application/rdf+xml'
                elif fmt == 'ttl':
                    data = await graph.ttlize()
                    ctype = MIME_TTL
                else:
                    return await self.msgError(error='Invalid format')

                if compress == 'gzip':
                    ctype = 'application/gzip'

                    return web.Response(
                        content_type=ctype,
                        body=zlib.compress(data)
                    )
                else:
                    return web.Response(
                        content_type=ctype,
                        text=data.decode()
                    )
            except Exception as err:
                log.debug(f'Export error: {err}')
                return await self.msgError(error='Export error')

    def isAllowedSparqlQuery(self, query: str):
        try:
            parseQuery(query)
            return True
        except Exception:
            return False

    async def sparql(self, request):
        """
        Run a SparQL query on the graph associated with the
        P2P service, and return the results in JSON format
        """

        async with self.throttler:
            acceptl = request.headers.get(
                'Accept',
                'application/json'
            ).split(',')

            try:
                auth = BasicAuth.decode(
                    auth_header=request.headers[hdrs.AUTHORIZATION]
                )

                assert auth.login is not None
                assert await self.peerAuthorized(
                    request,
                    auth,
                    loopTime()
                ) is True
            except (BaseException, ValueError):
                return await self.msgError(error='Invalid auth',
                                           status=401)

            try:
                post = await request.post()
                q = post['query']
            except Exception:
                q = request.query.get('query')

            try:
                assert isinstance(q, str)
                # assert self.isAllowedSparqlQuery(q) is True

                r = await self.app.loop.run_in_executor(
                    self.app.executor,
                    self.service.graph.query,
                    q
                )
                assert r is not None

                if 'application/json' in acceptl:
                    return web.json_response(
                        orjson.loads(
                            r.serialize(format='json')
                        ),
                        content_type=MIME_RESULTS_JSON,
                        status=200
                    )
                elif MIME_JSONLD in acceptl:
                    g = BaseGraph()
                    g.parse(
                        r.serialize(format='xml'), format='xml'
                    )

                    return web.json_response(
                        orjson.loads(
                            g.serialize(format='json-ld')
                        ),
                        content_type=MIME_JSONLD,
                        status=200
                    )
                elif 'application/xml' in acceptl or MIME_RDFXML in acceptl:
                    return web.Response(
                        body=r.serialize(format='xml'),
                        content_type=MIME_RDFXML
                    )
                elif MIME_TTL in acceptl or MIME_XTTL in acceptl:
                    return web.Response(
                        body=r.serialize(
                            format='turtle',
                            media_type=MIME_TTL
                        ),
                        content_type=MIME_TTL
                    )
                elif MIME_N3 in acceptl:
                    return web.Response(
                        body=r.serialize(format='n3'),
                        content_type=MIME_N3
                    )
                else:
                    raise Exception('Invalid Accept header')
            except Exception as err:
                log.debug(f'Query error: {err}')

                return await self.msgError(error='Invalid query')


class SmartQLAuthMiddleware(BasicAuthMiddleware):
    """
    Simple password-based auth middleware for the SparQL p2p service
    """

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

        self._sUser = 'smartql'
        self._sPassword = secrets.token_hex(16)

    @property
    def smartqlUser(self):
        return self._sUser

    @property
    def smartqlPassword(self):
        return self._sPassword

    async def check_credentials(self, username, password, request):
        return username == self.smartqlUser and \
            password == self.smartqlPassword


class SmartQLPeerBasedAuthMiddleware(BasicAuthMiddleware):
    """
    Peer-based auth middleware
    """

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

        self.__cache = TTLCache(32, 60)
        self.__blacklist = collections.deque([], 32)

    def passwordForPeer(self, peerId: str):
        pwd = self.__cache.get(peerId)

        if not pwd:
            self.__cache[peerId] = secrets.token_hex(16)

        return self.__cache[peerId]

    async def check_credentials(self, username, password, request):
        """
        Here username is the PeerID
        """

        if not isinstance(username, str) or len(username) > 128:
            self.__blacklist.append(username)

            log.debug('SmartQL auth: invalid username input')
            return False

        if username not in self.__cache or username in self.__blacklist:
            log.debug('SmartQL auth: wrong or blacklisted username')
            return False

        if self.__cache.get(username) == password:
            return True

        return False


class P2PSmartQLService(P2PService):
    """
    SparQL IPFS P2P service

    The P2P service name is in the following form:

        /x/smartql/{chain-env}/{graph-iri}/{proto-version}

    e.g "/x/smartql/beta/urn:ig:graph0/1.1"

    """

    def __init__(self, chainEnv, graph, config=None):
        self.graph = graph
        self.config = config if config else SparQLServiceConfig()

        self.mwAuth = SmartQLPeerBasedAuthMiddleware()

        super().__init__(
            'smartql',
            listenerClass=SparQLListener,
            description='SmartQL service',
            protocolName=f'smartql/{chainEnv}/{graph.identifier}',
            protocolVersion='1.1',
            listenRange=('127.0.0.1', range(49462, 49482)),
        )


class SparQLListener(P2PListener):
    async def createServer(self, host='127.0.0.1', portRange=[]):
        for port in portRange:
            try:
                self.handler = SparQLSiteHandler(self.service)

                self.webapp = SparQLWebApp(
                    middlewares=[self.service.mwAuth]
                )

                # SparQL endpoint: Support GET and POST
                self.webapp.router.add_get('/sparql', self.handler.sparql)
                self.webapp.router.add_post('/sparql', self.handler.sparql)

                self.webapp.router.add_get('/export', self.handler.export)

                # SmartQL endpoints
                self.webapp.router.add_route(
                    '*',
                    r'/resource/{rsc}/graph',
                    self.handler.resource
                )

                server = await self.loop.create_server(
                    self.webapp.make_handler(debug=True), host, port)

                log.debug('SmartQL service (port: {port}): started'.format(
                    port=port))
                self._server = server
                return (host, port)
            except Exception as err:
                log.debug(f'Could not start service: {err}')
                continue
