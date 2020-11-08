import collections
import weakref
import secrets
import orjson

from asyncio_throttle import Throttler

from galacteek.ipfs.tunnel import P2PListener
from galacteek.ipfs import ipfsOp
from galacteek.ipfs.p2pservices import P2PService
from galacteek.ipfs.cidhelpers import IPFSPath

from galacteek.core import jsonSchemaValidate
from galacteek.core.asynclib import loopTime
from galacteek.core.ps import psSubscriber
from galacteek.core import sha256Digest
from galacteek.core import uid4

from galacteek.core.captcha import randomCaptchaIpfs

from galacteek import log

import aiohttp
from aiohttp import web


pSubscriber = psSubscriber('rendezvous')


rvSchema = {
    'title': 'RV request',
    'type': 'object',
    'properties': {
        'peer': {
            'type': 'string',
            'pattern': r'[\w]{46,80}'
        },
        'msgtype': {
            'type': 'string'
        }
    },
    'required': ['peer', 'msgtype']
}

MSGTYPE_CAPTCHA_CHALLENGE = 'captchaChallenge'
MSGTYPE_CAPTCHA_SOLVE = 'captchaSolve'
MSGTYPE_RENDEZVOUS = 'rendezVous'
MSGTYPE_ACKWAIT = 'ackWait'

MSGF_SESSIONID = 'sessionId'
MSGF_CAPTCHACID = 'captchaCid'
MSGF_CAPTCHA = 'captcha'
MSGF_RVTOPIC = 'rvTopic'


class PSRendezVousWebApp(web.Application):
    pass


class PSRendezVousSiteHandler:
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
    async def rendezVous(self, ipfsop, request):
        async with self.throttler:
            try:
                js = await request.json()
                if not js or not isinstance(js, dict):
                    return await self.msgError()

                peerId = js.get('peer')
                token = js.get('sessiontoken')
                peerCtx = ipfsop.ctx.peers.getByPeerId(peerId)

                if not peerCtx:
                    raise Exception('Invalid peer')
            except Exception as err:
                return await self.msgError(status=401)

            chans = self.service.psChannels.setdefault(peerId, [])
            psId = sha256Digest(secrets.token_hex(32))
            chans.append(psId)
            topic = f'galacteek.rv.{psId}'

            await self.service.videoChatStartReceiver(topic)

            return web.json_response({
                'topic': topic
            })

    def generatePubsubTopic(self):
        psId = sha256Digest(secrets.token_hex(32))
        return f'galacteek.rendezvous.{psId}'

    @ipfsOp
    async def rendezVousWs(self, ipfsop, request):
        async with self.throttler:
            ws = web.WebSocketResponse()
            await ws.prepare(request)

            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self.processWsMessage(ipfsop, ws, msg)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    pass

            return ws

    async def processWsMessage(self, ipfsop, ws, msg):
        try:
            msg = orjson.loads(msg.data)
            print(msg)
            if not jsonSchemaValidate(msg, rvSchema):
                raise Exception('Invalid message')

            peerId = msg['peer']
            pRvSessions = self.service.rvSessions.setdefault(peerId, {})

            if msg['msgtype'] == 'init':
                uid = uid4()
                secret, cCid = await randomCaptchaIpfs()

                print('generated captcha with cid', secret, cCid)

                pRvSessions[uid] = {
                    'secret': secret,
                    MSGF_CAPTCHACID: cCid,
                    'solveAttempts': 0,
                    MSGF_RVTOPIC: None
                }

                await ws.send_json({
                    'msgtype': MSGTYPE_CAPTCHA_CHALLENGE,
                    MSGF_SESSIONID: uid,
                    MSGF_CAPTCHACID: cCid
                })
            elif msg['msgtype'] == MSGTYPE_CAPTCHA_SOLVE:
                sessionId = msg.get(MSGF_SESSIONID)
                captcha = msg.get(MSGF_CAPTCHA)

                if not sessionId or sessionId not in pRvSessions:
                    # XXX
                    return

                sess = pRvSessions[sessionId]

                print('received captcha solve', captcha)

                if captcha == sess['secret']:
                    # OK

                    await ws.send_json({
                        'msgtype': MSGTYPE_ACKWAIT
                    })

                    # TODO:
                    # Create UI ack request (with asyncio event ?)
                    # when user accepts then send the rv topic

                    await ipfsop.sleep(5)

                    sess['rvTopic'] = self.generatePubsubTopic()

                    await ws.send_json({
                        'msgtype': MSGTYPE_RENDEZVOUS,
                        MSGF_RVTOPIC: sess['rvTopic']
                    })

                    await self.service.videoChatStartReceiver(sess['rvTopic'])
                else:
                    sess['solveAttempts'] += 1

                    await ws.send_json({
                        'msgtype': 'error'
                    })

        except Exception:
            await ws.send_json({
                'msgtype': 'error'
            })


class PSRendezVousService(P2PService):
    def __init__(self):
        super().__init__(
            'ps-rendezvous',
            'RendezVous service',
            'ps-rendezvous',
            ('127.0.0.1', range(49462, 49472)),
            None
        )

        self.psChannels = {}
        self.rvSessions = {}

    @ipfsOp
    async def createListener(self, ipfsop):
        self._listener = PSRendezVousListener(
            self,
            ipfsop.client,
            self.protocolName,
            self.listenRange,
            None,
            loop=ipfsop.ctx.loop
        )
        addr = await self.listener.open()
        log.debug(
            f'RendezVous service: created listener at address {addr}')
        return addr is not None

    @ipfsOp
    async def videoChatStartReceiver(self, ipfsop, psTopic):
        rootPath = IPFSPath(ipfsop.ctx.resources['videocall']['Hash'])
        offerPath = rootPath.child('answer.html')
        offerPath.fragment = psTopic

        tab = self.app.mainWindow.addBrowserTab()
        tab.browseFsPath(offerPath)


class PSRendezVousListener(P2PListener):
    async def createServer(self, host='127.0.0.1', portRange=[]):
        for port in portRange:
            try:
                self.app = PSRendezVousWebApp()
                self.handler = PSRendezVousSiteHandler(self.service)

                self.app.router.add_post(
                    '/rendezVous', self.handler.rendezVous)
                self.app.router.add_get(
                    '/rendezVousWs', self.handler.rendezVousWs)

                server = await self.loop.create_server(
                    self.app.make_handler(debug=True), host, port)

                log.debug(f'RendezVous service (port: {port}): started')
                self._server = server
                return (host, port)
            except Exception:
                continue
