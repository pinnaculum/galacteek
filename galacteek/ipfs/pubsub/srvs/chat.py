import asyncio
import aiorwlock
import orjson

from galacteek import log
from galacteek.ipfs.pubsub import TOPIC_CHAT
from galacteek.ipfs.pubsub import TOPIC_ENC_CHAT

from galacteek.ipfs.pubsub.service import JSONPubsubService
from galacteek.ipfs.pubsub.service import RSAEncryptedJSONPubsubService

from galacteek.ipfs.pubsub.messages.chat import ChatRoomMessage
from galacteek.ipfs.pubsub.messages.chat import ChatStatusMessage
from galacteek.ipfs.pubsub.messages.chat import ChatChannelsListMessage
from galacteek.ipfs.pubsub.messages.chat import UserChannelsListMessage
from galacteek.ipfs.wrappers import ipfsOp

from galacteek.core.ps import keyChatChannels
from galacteek.core.ps import keyChatChanList
from galacteek.core.ps import keyChatChanUserList
from galacteek.core.ps import makeKeyPubChatTokens
from galacteek.core.ps import mSubscriber
from galacteek.core.pubchattokens import PubChatTokensManager


def encChatChannelTopic(channel):
    return f'{TOPIC_ENC_CHAT}.{channel}'


def chatChannelTopic(channel):
    return f'{TOPIC_CHAT}.{channel}'


class PSChatService(JSONPubsubService):
    def __init__(self, ipfsCtx, client, **kw):
        super().__init__(ipfsCtx, client, topic=TOPIC_CHAT,
                         runPeriodic=True,
                         filterSelfMessages=False, **kw)
        self.lock = aiorwlock.RWLock()
        mSubscriber.add_async_listener(
            keyChatChanList, self.onUserChannelList)

        self.chanUsers = {}
        self.tokManager = PubChatTokensManager()

        self.tokManager.sChanChanged.connectTo(self.onChanChanged)
        self.tokManager.sTokenStatus.connectTo(self.onTokenStatus)

    async def start(self):
        await super().start()

        await self.tokManager.start()
        await self.scheduler.spawn(self.tokManager.cleanupTask())

    async def onChanChanged(self, pubchannel):
        await self.chatChanUserListPub(pubchannel)

    async def onTokenStatus(self, tokenCid, channel, status):
        key = makeKeyPubChatTokens(channel)
        await self.gHubPublish(
            key,
            (tokenCid, status)
        )

    async def peersByChannel(self, channel):
        async for token in self.tokManager.tokensByChannel(channel):
            yield token.peerId, token

    async def processJsonMessage(self, sender, msg):
        msgType = msg.get('msgtype', None)

        peerCtx = self.ipfsCtx.peers.getByPeerId(sender)
        if not peerCtx:
            self.debug('Message from unauthenticated peer: {}'.format(
                sender))
            return

        if msgType == ChatChannelsListMessage.TYPE:
            await self.handleChannelsListMessage(msg)

        elif msgType == UserChannelsListMessage.TYPE:
            await self.handleUserChannelsMessage(sender, peerCtx, msg)

    @ipfsOp
    async def onUserChannelList(self, ipfsop, key, msg):
        await self.send(msg)

    async def chatChanUserListPub(self, chan):
        pList = [p async for p in self.peersByChannel(chan)]

        await self.gHubPublish(
            keyChatChanUserList,
            (chan, pList)
        )

    @ipfsOp
    async def handleUserChannelsMessage(self, ipfsop, sender, piCtx, msg):
        cMsg = UserChannelsListMessage(msg)
        if not cMsg.valid():
            self.debug(f'Invalid UserChannelsListMessage from {sender}')
            return

        senderChans = cMsg.pubChannels if cMsg.pubChannels else []
        jwsCids = [c['sessionJwsCid'] for c in senderChans]

        # pChans = self.chanUsers.setdefault(sender, {})
        # lastrev = pChans.get('_lastrev')

        for jwsCid in jwsCids:
            token = await self.tokManager.tokenGet(jwsCid)

            if token:
                await self.tokManager.tokenUpdate(jwsCid)
            else:
                # Fetch the JWS first
                jws = await ipfsop.getJson(jwsCid, timeout=5)

                if not jws:
                    log.debug(f'Could not fetch JWS with CID: {jwsCid}')
                    await ipfsop.sleep()
                    continue

                pubJwk = await piCtx.pubKeyJwk()
                if not pubJwk:
                    log.debug(f'Peer {sender}: waiting for JWK')
                    await ipfsop.sleep()
                    continue

                payload = await ipfsop.ctx.rsaExec.jwsVerify(
                    orjson.dumps(jws).decode(),
                    pubJwk
                )

                if not payload:
                    await ipfsop.sleep()
                    continue

                try:
                    # Decoded the token payload
                    decoded = orjson.loads(payload.decode())
                    assert 'did' in decoded
                    assert 'channel' in decoded
                    assert 'psTopic' in decoded

                    psTopic = decoded['psTopic']
                    chan = decoded['channel']
                except Exception as err:
                    log.debug(f'Peer {sender}: invalid JWS: {err}')
                    await ipfsop.sleep()
                    continue
                else:
                    log.debug(f'Peer {sender}: valid JWS:'
                              f'sec topic: {psTopic}')

                if ipfsop.ourNode(sender):
                    async with self.lock.writer_lock:
                        await self.tokManager.reg(
                            jwsCid, chan, psTopic, sender)
                else:
                    # Check who's subscribed on the topic
                    psPeers = await ipfsop.pubsubPeers(
                        topic=psTopic, timeout=4)

                    # There should only be one peer subscribed
                    if psPeers and len(psPeers) > 0:
                        async with self.lock.writer_lock:
                            await self.tokManager.reg(
                                jwsCid, chan, psTopic, sender)

            await ipfsop.sleep()

    @ipfsOp
    async def handleChannelsListMessage(self, ipfsop, msg):
        cMsg = ChatChannelsListMessage(msg)
        if not cMsg.valid():
            self.debug('Invalid channels message')
            return

        self.debug('Received valid chat channels list message')

        # Publish to the hub
        await self.gHubPublish(keyChatChannels, cMsg)

    @ipfsOp
    async def periodic(self, ipfsop):
        while True:
            await asyncio.sleep(90)

            if ipfsop.ctx.currentProfile:
                channelsDag = ipfsop.ctx.currentProfile.dagChatChannels

                await self.send(
                    ChatChannelsListMessage.make(channelsDag.channelsSorted)
                )

            await self.tokManager.cleanup()

    async def shutdown(self):
        await super().shutdown()
        self.tokManager.active = False
        await asyncio.sleep(0.5)


class PSEncryptedChatChannelService(RSAEncryptedJSONPubsubService):
    def __init__(self, ipfsCtx, client,
                 channel: str, topic: str,
                 jwsTokenCid, psKey, **kw):
        self.channel = channel
        self.psKey = psKey
        self.jwsTokenCid = jwsTokenCid
        self._chatPeers = []
        self.mChatService = ipfsCtx.pubsub.byTopic(TOPIC_CHAT)

        super().__init__(ipfsCtx, client,
                         topic,
                         runPeriodic=True,
                         peered=False,
                         minMsgTsDiff=1,
                         filterSelfMessages=False, **kw)

    async def processJsonMessage(self, sender, msg):
        msgType = msg.get('msgtype', None)

        peerCtx = self.ipfsCtx.peers.getByPeerId(sender)
        if not peerCtx:
            self.debug('Message from unauthenticated peer: {}'.format(
                sender))
            return

        if msgType == ChatRoomMessage.TYPE:
            await self.handleChatMessage(sender, peerCtx, msg)

    async def handleChatMessage(self, sender, peerCtx, msg):
        cMsg = ChatRoomMessage(msg)
        if not cMsg.valid():
            self.debug('Invalid chat message')
            return

        cMsg.peerCtx = peerCtx
        await self.gHubPublish(self.psKey, (sender, cMsg))

    async def peersToSend(self):
        async for peer, token in self.mChatService.peersByChannel(
                self.channel):
            piCtx = self.ipfsCtx.peers.getByPeerId(peer)
            if not piCtx:
                continue

            topic = token.secTopic
            yield (peer, piCtx, None, topic)

    async def processHeartbeat(self, sender, message):
        if sender not in self._chatPeers:
            self._chatPeers.append(sender)

    async def handleStatusMessage(self, sender, peerCtx, msg):
        sMsg = ChatStatusMessage(msg)
        if not sMsg.valid():
            self.debug('Invalid chat message')
            return

        sMsg.peerCtx = peerCtx
        await self.gHubPublish(self.psKey, sMsg)

    async def shutdown(self):
        await super().shutdown()
        await self.mChatService.tokManager.tokenDestroy(self.jwsTokenCid)
