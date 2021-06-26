import orjson

from asyncio_throttle import Throttler

from galacteek.ipfs.tunnel import P2PListener
from galacteek.ipfs.p2pservices import P2PService
from galacteek.core import runningApp
from galacteek import log

from aiohttp import web


class SparQLWebApp(web.Application):
    pass


class SparQLSiteHandler:
    """
    SparQL HTTP service coroutines
    """

    def __init__(self, service):
        self.throttler = Throttler(
            rate_limit=30,
            period=5.0,
            retry_interval=2.0
        )
        self.service = service
        self.app = runningApp()

    async def msgError(self, error='Invalid request', status=500):
        return web.json_response({
            'error': error
        }, status=status)

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
                post = await request.post()
                q = post['query']
            except Exception:
                q = request.query.get('query')

            try:
                assert isinstance(q, str)

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
                        status=200
                    )
                elif 'application/xml' in acceptl:
                    return web.Response(
                        body=r.serialize(format='xml'),
                        content_type='application/xml'
                    )
                else:
                    raise Exception('Invalid Accept header')
            except Exception:
                return await self.msgError(error='Invalid query')


class P2PSparQLService(P2PService):
    """
    SparQL IPFS P2P service

    The P2P service name is in the following form:

        /x/sparql/{graph-iri}/{proto-version}

    e.g "/x/sparql/urn:ig:graph0/1.0"

    """

    def __init__(self, graph):
        self.graph = graph
        super().__init__(
            'sparql',
            listenerClass=SparQLListener,
            description='SPARQL service',
            protocolName=f'sparql/{graph.identifier}',
            protocolVersion='1.0',
            listenRange=('127.0.0.1', range(49462, 49482)),
        )


class SparQLListener(P2PListener):
    async def createServer(self, host='127.0.0.1', portRange=[]):
        for port in portRange:
            try:
                self.webapp = SparQLWebApp()
                self.handler = SparQLSiteHandler(self.service)

                # Support GET and POST
                self.webapp.router.add_get('/sparql', self.handler.sparql)
                self.webapp.router.add_post('/sparql', self.handler.sparql)

                server = await self.loop.create_server(
                    self.webapp.make_handler(debug=True), host, port)

                log.debug('SparQL service (port: {port}): started'.format(
                    port=port))
                self._server = server
                return (host, port)
            except Exception:
                continue
