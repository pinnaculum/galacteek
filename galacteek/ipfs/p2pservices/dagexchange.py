import collections
import weakref

from asyncio_throttle import Throttler

from galacteek.ipfs.tunnel import P2PListener
from galacteek.ipfs import ipfsOp
from galacteek.ipfs.p2pservices import P2PService
from galacteek.core import jsonSchemaValidate
from galacteek.core.asynclib import loopTime
from galacteek.core.ps import psSubscriber
from galacteek.core.ps import keyTokensDagExchange
from galacteek.core.ps import keySnakeDagExchange
from galacteek import log

from aiohttp import web


pSubscriber = psSubscriber('p2p_dagexchange')


dagCidSignSchema = {
    'title': 'DAG CID sign request',
    'type': 'object',
    'properties': {
        'elixir': {
            'type': 'string',
            'pattern': r'[a-f0-9]{64}'
        },
        'sessiontoken': {
            'type': 'string',
            'pattern': r'[a-f0-9]{64,128}'
        }
    },
    'required': ['elixir', 'sessiontoken']
}


class DAGExchangeWebApp(web.Application):
    pass


class DAGExchangeSiteHandler:
    def __init__(self, service):
        self.service = service
        self.throttler = Throttler(
            rate_limit=10,
            period=5.0,
            retry_interval=2.0
        )

    def message(self, msg, level='debug'):
        getattr(log, level)(msg)

    async def msgError(self, error='Invalid request', status=500):
        return web.json_response({
            'error': error
        }, status=status)

    @ipfsOp
    async def dagCidSign(self, ipfsop, request):
        async with self.throttler:
            try:
                js = await request.json()
                if not js or not isinstance(js, dict):
                    return await self.msgError()

                if not jsonSchemaValidate(js, dagCidSignSchema):
                    raise Exception('Invalid req schema')

                elixir = js.get('elixir')
                token = js.get('sessiontoken')

                if token != self.service._token:
                    raise Exception('Invalid token')

                cid = None
                for msg in self.service.elixirs:
                    try:
                        head = msg['snakeoil'][0:64]
                        tail = msg['snakeoil'][64:128]

                        if elixir == head:
                            cid = msg['cids'][0]
                            log.debug(f'Head: {head}: {cid}')
                            break
                        elif elixir == tail:
                            cid = msg['cids'][1]
                            log.debug(f'Tail: {tail}: {cid}')
                            break
                        else:
                            continue
                    except Exception as err:
                        log.debug(f'Error searching elixirs: {err}')
                        continue

                if not cid:
                    raise Exception('CID not found')

                if not self.service.cidRequestable(cid):
                    log.debug(f'Asked to sign CID {cid} but not requestable')
                    raise Exception('CID not requestable')
            except Exception as err:
                self.message(f'Unauthorized request: {err}')
                return await self.msgError(status=401)

            self.message('Received CID sign request for CID: {}'.format(
                cid))

            try:
                signed = await ipfsop.rsaAgent.pssSign64(cid.encode())

                if signed:
                    return web.json_response({
                        cid: {
                            'pss64': signed
                        }
                    })
                else:
                    raise Exception('Cannot sign CID')
            except Exception:
                return await self.msgError()


class DAGExchangeService(P2PService):
    """
    NASDAQ sucks ... What about the ..

    InterPlanetary Signature Service of Directed Acyclic Graphs
    """

    def __init__(self):
        super().__init__(
            'dagexchange',
            description='DAG Exchange service',
            protocolName='dagexchange',
            listenRange=('127.0.0.1', range(49452, 49462))
        )

        self.__edags = weakref.WeakValueDictionary()
        self.elixirs = collections.deque([], 12)

        self._token = None

        pSubscriber.add_sync_listener(
            keyTokensDagExchange, self.onDagExchangeToken)
        pSubscriber.add_sync_listener(
            keySnakeDagExchange, self.onPureSnakeOil)

    def onDagExchangeToken(self, key, message):
        self._token = message['token']
        log.debug(f'Switched service token: {self._token}')

    def onPureSnakeOil(self, key, message):
        log.debug(f'Storing new elixir: {message}')
        self.elixirs.appendleft(message)
        self.purgeExpiredElixirs()

    def purgeExpiredElixirs(self):
        lTime = loopTime()

        for msg in list(self.elixirs):
            if not isinstance(msg, dict):
                continue

            if 'expires' in msg and lTime > msg['expires']:
                log.debug('Purging old message')
                self.elixirs.remove(msg)

    def cidRequestable(self, cid: str):
        """
        Checks if we allow to sign a given CID.
        Latest CID and 8 previous CIDs in EDAG history are OK
        """

        for dagMetaPath, edag in self.__edags.items():
            try:
                if edag.dagCid == cid:
                    return True

                dMeta = edag.dagMeta
                if isinstance(dMeta, dict) and 'history' in dMeta:
                    if cid in dMeta['history'][0:8]:
                        return True
            except Exception as err:
                log.debug(f'cidRequestable({cid}): '
                          f'{dagMetaPath}: unknown error: {err}')
                continue

        return False

    def allowEDag(self, edag):
        if edag.dagMetaMfsPath not in self.__edags:
            log.debug(f'Allowing signing for DAG {edag.dagMetaMfsPath}')
            self.__edags[edag.dagMetaMfsPath] = edag

    @ipfsOp
    async def createListener(self, ipfsop):
        self._listener = DAGExchangeListener(
            self,
            ipfsop.client,
            self.protocolName,
            self.listenRange,
            None,
            loop=ipfsop.ctx.loop
        )
        addr = await self.listener.open()
        log.debug(
            f'DAG Exchange service: created listener at address {addr}')
        return addr is not None


class DAGExchangeListener(P2PListener):
    async def createServer(self, host='127.0.0.1', portRange=[]):
        for port in portRange:
            try:
                self.app = DAGExchangeWebApp()
                self.handler = DAGExchangeSiteHandler(self.service)

                self.app.router.add_post(
                    '/dagcidsign', self.handler.dagCidSign)

                server = await self.loop.create_server(
                    self.app.make_handler(debug=True), host, port)

                log.debug(f'DAG Exchange service (port: {port}): started')
                self._server = server
                return (host, port)
            except Exception:
                continue
