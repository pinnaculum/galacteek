import asyncio
import secrets

from galacteek import AsyncSignal

from galacteek.ipfs.pubsub import TOPIC_LD_PRONTO
from galacteek.ipfs.pubsub.service import JSONPubsubService
from galacteek.ipfs.pubsub.messages.ld import *


class RDFBazaarService(JSONPubsubService):
    def __init__(self, ipfsCtx, **kw):
        self._igraphs = kw.pop('igraphs', {})

        super().__init__(ipfsCtx, TOPIC_LD_PRONTO,
                         runPeriodic=False,
                         filterSelfMessages=True, **kw)

        self.__serviceToken = secrets.token_hex(64)

        self.sExch = AsyncSignal(RDFGraphsExchangeMessage)
        self.sSparql = AsyncSignal(SparQLHeartbeatMessage)

    async def processJsonMessage(self, sender, msg, msgDbRecord=None):
        msgType = msg.get('msgtype', None)

        peerCtx = self.ipfsCtx.peers.getByPeerId(sender)
        if not peerCtx:
            self.debug('Message from unauthenticated peer: {}'.format(
                sender))
            return

        if msgType in SparQLHeartbeatMessage.VALID_TYPES:
            await self.handleSparqlMessage(sender, msg, msgDbRecord)

    async def handleSparqlMessage(self, sender, msg, msgDbRecord):
        sMsg = SparQLHeartbeatMessage(msg)

        if sMsg.valid():
            await self.sSparql.emit(sMsg)

    async def handleExchangeMessage(self, sender, msg, msgDbRecord):
        eMsg = RDFGraphsExchangeMessage(msg)

        if not eMsg.valid():
            self.debug('Invalid exchange message')
            return

        await self.sExch.emit(eMsg)

    async def periodic(self):
        while True:
            await asyncio.sleep(20)

            # msg = RDFGraphsExchangeMessage.make(self._igraphs)
            # await self.send(msg)
