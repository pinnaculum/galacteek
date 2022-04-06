import orjson
import asyncio
import time
import collections
import traceback
import base64

from galacteek import log as logger
from galacteek import AsyncSignal
from galacteek import ensureLater

from galacteek.core.asynclib import GThrottler

from galacteek.config import cParentGet
from galacteek.config import configModRegCallback
from galacteek.config import Configurable
from galacteek.config import merge as configMerge

from galacteek.ipfs.pubsub import TOPIC_MAIN
from galacteek.ipfs.pubsub import TOPIC_HASHMARKS
from galacteek.ipfs.pubsub import MsgAttributeRecordError

from galacteek.ipfs.pubsub.messages.core import PubsubMessage
from galacteek.ipfs.pubsub.messages.core import MarksBroadcastMessage

from galacteek.ipfs.wrappers import ipfsOp

from galacteek.core.asynclib import loopTime
from galacteek.core.asynclib import asyncify
from galacteek.core.asynclib import async_enterable
from galacteek.core.ipfsmarks import IPFSMarks

from galacteek.core.ps import keyPsJson
from galacteek.core.ps import keyPsEncJson
from galacteek.core.ps import psSubscriber
from galacteek.core.ps import gHub

from galacteek.database.psmanager import psManagerForTopic

from galacteek.services import GService

import aioipfs
from aioipfs.exceptions import IPFSConnectionError


psServSubscriber = psSubscriber('pubsubServices')


PS_ENCTYPE_NULL = 0
PS_ENCTYPE_JSON_RAW = 1
PS_ENCTYPE_RSA_AES = 2
PS_ENCTYPE_CURVE25519 = 3


class MsgSpy(object):
    def __init__(self, psDbManager, msgRecord, msgType, name, value):
        self.psDbManager = psDbManager
        self.msgType = msgType
        self.attrName = name
        self.value = value
        self.msgRecord = msgRecord

    async def __aenter__(self):
        entries = await self.psDbManager.searchMsgAttribute(
            self.msgType,
            self.attrName,
            self.value
        )
        self.found = len(entries) > 0

        if self.found:
            raise MsgAttributeRecordError(
                f'{self.msgType}: {self.attrName} exists')

        return self

    async def __aexit__(self, *args):
        if not self.found:
            self.rec = await self.psDbManager.recordMsgAttribute(
                self.msgRecord,
                self.msgType,
                self.attrName,
                self.value
            )


class PubsubService(Configurable, GService):
    """
    Generic IPFS pubsub service
    """

    hubPublish = True
    encodingType = PS_ENCTYPE_NULL

    def __init__(self,
                 ipfsCtx,
                 topic='galacteek.default',
                 runPeriodic=False, filterSelfMessages=True,
                 maxMsgTsDiff=None, minMsgTsDiff=None,
                 maxMessageSize=32768,
                 scheduler=None,
                 serveLifetime=0,
                 metrics=True,
                 peered=False,
                 **kw):
        self.throttler = None

        self.ipfsCtx = ipfsCtx
        self.topicBase = topic
        self.inQueue = asyncio.Queue(maxsize=256)
        self.errorsQueue = asyncio.Queue()
        self.lock = asyncio.Lock()
        self.peered = peered
        self.scheduler = scheduler

        self._filterSelfLegacy = filterSelfMessages
        self._receivedCount = 0
        self._errorsCount = 0
        self._runPeriodic = runPeriodic
        self._filters = []
        self._peerActivity = {}
        self._ltServeStart = 0
        self._serveLifetime = serveLifetime  # in seconds
        self._metrics = metrics

        GService.__init__(self, **kw)
        Configurable.__init__(self, applyNow=True)

        self._shuttingDown = False

        # Async sigs
        self.rawMessageReceived = AsyncSignal(str, str, bytes)
        self.rawMessageSent = AsyncSignal(str, str, str)

        self.tskServe = None
        self.tskProcess = None
        self.tskPeriodic = None

        self.addMessageFilter(self.filterMessageSize)
        self.addMessageFilter(self.filterPeerActivity)

        configModRegCallback(self.onConfigChanged,
                             mod='galacteek.ipfs.pubsub')

    @property
    def receivedCount(self):
        return self._receivedCount

    @property
    def errorsCount(self):
        return self._errorsCount

    @property
    def runPeriodic(self):
        return self._runPeriodic

    def config(self):
        return cParentGet('serviceTypes.base')

    def topic(self):
        if self.peered:
            peerId = self.ipfsCtx.node.id
            return f'{self.topicBase}.{peerId}'
        else:
            return self.topicBase

    def messageConfig(self, messageType: str):
        cfg = self.config()
        try:
            return cfg.messages.get(messageType)
        except Exception:
            return None

    def configApply(self, cfg):
        if not self.throttler:
            self.throttler = GThrottler(
                rate_limit=cfg.throttler.rateLimit,
                period=cfg.throttler.period,
                retry_interval=cfg.throttler.retryInterval,
                name=cfg.throttler.name
            )
        else:
            self.throttler.rate_limit = cfg.throttler.rateLimit
            self.throttler.period = cfg.throttler.period
            self.throttler.retry_interval = cfg.throttler.retryInterval

        self._minMsgTsDiff = cfg.filters.timeStampDiff.min
        self._maxMsgTsDiff = cfg.filters.timeStampDiff.max

        if cfg.filters.messageSize:
            self._maxMessageSize = cfg.filters.messageSize.max
        else:
            self._maxMessageSize = 0

        if cfg.filters.filterSelf.enabled and self._filterSelfLegacy:
            self.addMessageFilter(self.filterSelf)

    def debug(self, msg):
        logger.debug('PS[{0}]: {1}'.format(self.topic(), msg))

    def info(self, msg):
        logger.info('PS[{0}]: {1}'.format(self.topic(), msg))

    def logStatus(self):
        self.debug('** Messages received: {0}, errors: {1}'.format(
            self.receivedCount, self.errorsCount))

    async def on_stop(self):
        await super().on_stop()

        await self.stopListening()

    async def restartProcessTask(self):
        if self.tskProcess:
            await self.tskProcess.close()

        self.tskProcess = await self.scheduler.spawn(self.processMessages())

    async def event_g_services_app(self, key, message):
        event = message['event']

        if event['type'] == 'IpfsOperatorChange':
            await self.stopListening()

            await asyncio.sleep(0.9)

            await self.startListening()
        elif event['type'] == 'PubsubChannelForceStart':
            if event.get('topic') == self.topic():
                if not self.tskServe:
                    await self.startListening()

    @ipfsOp
    async def startListening(self, ipfsop):
        """ Create the different tasks for this service """

        self._shuttingDown = False

        self.debug(f'{self!r}: Start listening')

        if self.scheduler is None:
            raise Exception('No scheduler specified')

        self.tskServe = await self.scheduler.spawn(self.serve(ipfsop))
        self.tskProcess = await self.scheduler.spawn(self.processMessages())

        if self.runPeriodic:
            self.tskPeriodic = await self.scheduler.spawn(self.periodic())

        self.psDbManager = await psManagerForTopic(
            self.topic(), encType=self.encodingType)

    async def stopListening(self):
        self._shuttingDown = True

        await self.shutdown()

        if self.throttler:
            self.throttler.pause()

        for tsk in [self.tskServe, self.tskProcess, self.tskPeriodic]:
            if not tsk:
                continue

            try:
                await tsk.close(timeout=1.0)
            except asyncio.TimeoutError as tErr:
                self.debug(
                    'timeout while closing {task}: shutdown ERR: {err}'.format(
                        task=tsk, err=str(tErr)))
                continue
            except Exception as cErr:
                self.debug('task {task}: shutdown ERR: {err}'.format(
                    task=tsk, err=str(cErr)))
                continue
            else:
                self.debug('task {}: shutdown ok'.format(tsk))

    def addMessageFilter(self, filter):
        if filter not in self._filters:
            self._filters.append(filter)

    def filterMessageSize(self, msg):
        if len(msg['data']) > self._maxMessageSize:
            return True
        return False

    def filterPeerActivity(self, msg):
        ltime = loopTime()

        senderNodeId = msg['from'] if isinstance(msg['from'], str) else \
            msg['from'].decode()

        # Don't filter our messages
        if senderNodeId == self.ipfsCtx.node.id:
            return False

        if senderNodeId not in self._peerActivity:
            self._peerActivity[senderNodeId] = collections.deque([], 6)

        records = self._peerActivity[senderNodeId]
        records.appendleft((ltime, len(msg['data'])))

        if len(records) >= 2 and isinstance(self._minMsgTsDiff, int):
            latestIdx = len(records) - 1
            latest = records[latestIdx][0]
            previous = records[latestIdx - 1][0]

            latest = records[0][0]
            previous = records[1][0]

            if (latest - previous) < self._minMsgTsDiff:
                records.popleft()
                self.debug(f'Ignoring message from {senderNodeId}: '
                           f'Min TS diff {self._minMsgTsDiff} not reached')
                return True

        return False

    def filterSelf(self, msg):
        sender = msg['from'] if isinstance(msg['from'], str) else \
            msg['from'].decode()

        if sender == self.ipfsCtx.node.id:
            return True

        return False

    async def filtered(self, message):
        for filter in self._filters:
            if filter(message) is True:  # That means we drop it
                return True

        return False

    async def shutdown(self):
        pass

    async def processMessages(self):
        """ Messages processing task to be implemented in your listener """
        return True

    async def periodic(self):
        return True

    async def serve(self, ipfsop):
        """
        Subscribe to the pubsub topic, read and filter incoming messages
        (dropping the ones emitted by us). Selected messages are put on the
        async queue (inQueue) to be later treated in the processMessages() task
        """

        topic = self.topic()

        # We're only in the bytopic list when listening
        self.ipfsCtx.pubsub.reg(self)

        self._ltServeStart = loopTime()

        try:
            async for message in ipfsop.client.pubsub.sub(topic):
                if await self.filtered(message):
                    continue

                self.ipfsCtx.pubsub.psMessageRx.emit()
                if self._shuttingDown:
                    return

                await self.inQueue.put(message)

                self._receivedCount += 1
                await asyncio.sleep(0)

                # Check channel lifetime limits
                runtime = loopTime() - self._ltServeStart

                if self._serveLifetime > 0 and runtime > self._serveLifetime:
                    self.debug('Channel lifetime expired, byebye')
                    break
        except asyncio.CancelledError:
            self.ipfsCtx.pubsub.unreg(self)
            self.debug('Cancelled, queue size was {0}'.format(
                self.inQueue.qsize()))
            return
        except (Exception, IPFSConnectionError) as err:
            # Unregister
            self.ipfsCtx.pubsub.unreg(self)

            self.debug(
                f'Serve interrupted by unknown exception {err}')

            ensureLater(5, self.serve, ipfsop)
        else:
            await self.stopListening()

            self.ipfsCtx.pubsub.unreg(self)

    @ipfsOp
    async def send(self, ipfsop, msg, topic=None):
        """
        Publish a message

        :param msg: message or message payload
        """

        if topic is None:
            topic = self.topic()

        if issubclass(msg.__class__, PubsubMessage):
            data = str(msg)
        elif isinstance(msg, str):
            data = msg
        else:
            raise ValueError('Invalid message data')

        try:
            status = await ipfsop.client.pubsub.pub(topic, data)
            self.ipfsCtx.pubsub.psMessageTx.emit()
        except aioipfs.APIError:
            logger.debug('Could not send pubsub message to {topic}'.format(
                topic=topic))
        except Exception as err:
            logger.debug(f'Unknown error on pubsub send: {err}')
        else:
            return status

    async def gHubPublish(self, key, msg):
        gHub.publish(key, msg)

        await asyncio.sleep(0.05)

    @async_enterable
    async def msgSpy(self, dbRecord, msgType, attrName, value):
        return MsgSpy(
            self.psDbManager,
            dbRecord,
            msgType,
            attrName,
            value
        )


class JSONPubsubService(PubsubService):
    """
    JSON pubsub listener, handling incoming messages as JSON objects
    """

    encodingType = PS_ENCTYPE_JSON_RAW
    jsonMessageReceived = AsyncSignal(str, str, bytes)
    hubKey = keyPsJson

    def config(self):
        base = super().config()
        jsonConfig = cParentGet('serviceTypes.json')

        if jsonConfig:
            return configMerge(base, jsonConfig)

        return base

    def msgDataToJson(self, msg):
        """
        Decode JSON data contained in a pubsub message
        """
        try:
            return orjson.loads(msg['data'].decode())
        except Exception:
            logger.debug('Could not decode JSON message data')
            return None

    async def processMessages(self):
        try:
            asyncConv = getattr(self, 'asyncMsgDataToJson')
        except Exception:
            useAsyncConv = False
        else:
            useAsyncConv = asyncio.iscoroutinefunction(asyncConv)

        try:
            while not self._shuttingDown:
                data = await self.inQueue.get()

                if data is None:
                    continue

                async with self.throttler:
                    if self._shuttingDown:
                        return

                    if useAsyncConv is True:
                        msg = await asyncConv(data)
                    else:
                        msg = self.msgDataToJson(data)

                    if msg is None:
                        self.debug('Invalid JSON message')
                        continue

                    sender = data['from'] if isinstance(
                        data['from'], str) else data['from'].decode()

                    try:
                        if self.hubPublish:
                            gHub.publish(
                                self.hubKey, (sender, self.topic(), msg))

                        if self._metrics:
                            rec = await self.psDbManager.recordMessage(
                                sender,
                                len(data['data']),
                                seqNo=data['seqno']
                            )
                        else:
                            rec = None

                        await self.processJsonMessage(
                            sender, msg,
                            msgDbRecord=rec
                        )
                    except Exception as exc:
                        self.debug(
                            'processJsonMessage error: {}'.format(str(exc)))
                        traceback.print_exc()
                        await self.errorsQueue.put((msg, exc))
                        self._errorsCount += 1

                    self.inQueue.task_done()

        except asyncio.CancelledError:
            self.debug('JSON process cancelled')
        except Exception as err:
            self.debug('JSON process exception: {}'.format(
                str(err)))

    async def processJsonMessage(self, sender, msg, msgDbRecord=None):
        """ Implement this method to process incoming JSON messages"""
        return True


class JSONLDPubsubService(JSONPubsubService):
    """
    JSON-LD pubsub listener, handling incoming messages as JSON-LD
    """

    def __init__(self, *args, autoExpand=False, **kw):
        super(JSONLDPubsubService, self).__init__(*args, **kw)

        self.autoExpand = autoExpand

    @ipfsOp
    async def expand(self, ipfsop, data):
        try:
            async with ipfsop.ldOps() as ld:
                return await ld.expandDocument(data)
        except Exception:
            pass

    async def processJsonMessage(self, sender, msg, msgDbRecord=None):
        if self.autoExpand:
            expanded = await self.expand(msg)
            if expanded:
                return await self.processLdMessage(sender, expanded)
        else:
            JSONPubsubService.processJsonMessage(
                self, sender, msg, msgDbRecord=msgDbRecord)

    async def processLdMessage(self, sender, msg):
        return True


class PSHashmarksExchanger(JSONPubsubService):
    def __init__(self, ipfsCtx, marksLocal, marksNetwork):
        super(PSHashmarksExchanger, self).__init__(
            ipfsCtx,
            topic=TOPIC_HASHMARKS,
            runPeriodic=True,
            filterSelfMessages=True,
            maxMessageSize=131072,
            minMsgTsDiff=60 * 2)
        self.marksLocal = marksLocal
        self.marksNetwork = marksNetwork
        self.marksLocal.markAdded.connect(self.onMarkAdded)
        self._sendEvery = 60 * 8
        self._lastBroadcast = 0

    @property
    def curProfile(self):
        return self.ipfsCtx.currentProfile

    @asyncify
    async def onMarkAdded(self, path, mark):
        if mark['share'] is True:
            await self.broadcastSharedMarks()

    async def broadcastSharedMarks(self):
        try:
            sharedMarks = IPFSMarks(None, autosave=False)
            count = sharedMarks.merge(self.marksLocal, share=True, reset=True)

            if count > 0:
                self.debug('Sending shared hashmarks')
                msg = MarksBroadcastMessage.make(self.ipfsCtx.node.id,
                                                 sharedMarks.root)
                await self.send(str(msg))
                self._lastBroadcast = int(time.time())
        except BaseException:
            pass

    async def periodic(self):
        while True:
            await asyncio.sleep(self._sendEvery)
            await self.broadcastSharedMarks()

    async def processJsonMessage(self, sender, msg, msgDbRecord=None):
        msgType = msg.get('msgtype', None)
        if msgType == MarksBroadcastMessage.TYPE:
            try:
                await self.processBroadcast(sender, msg)
            except BaseException:
                pass

    async def processBroadcast(self, sender, msg):
        bMsg = MarksBroadcastMessage(msg)

        if not bMsg.valid():
            self.debug('Invalid broadcast message')
            return

        if not self.ipfsCtx.peers.peerRegistered(sender):
            self.debug(
                'Broadcast from unauthenticated peer: {0}'.format(sender))
            return

        marksJson = bMsg.marks
        if not marksJson:
            return

        marksCollection = IPFSMarks(None, data=marksJson, autosave=False)

        # JSON schema validation
        if not await marksCollection.isValidAsync():
            self.debug('Received invalid hashmarks from {sender}'.format(
                sender=sender))
            return
        else:
            self.debug('Hashmarks broadcast from {sender} is valid'.format(
                sender=sender))

        try:
            if self.curProfile:
                await self.curProfile.storeHashmarks(sender, marksCollection)
        except Exception:
            self.debug('Could not store data in hashmarks library')
        else:
            self.info('Stored hashmarks from peer: {0}'.format(sender))


class PSMainService(JSONPubsubService):
    def __init__(self, ipfsCtx, **kw):
        super(PSMainService, self).__init__(ipfsCtx, topic=TOPIC_MAIN, **kw)


class RSAEncryptedJSONPubsubService(JSONPubsubService):
    encodingType = PS_ENCTYPE_RSA_AES
    hubKey = keyPsEncJson

    def __init__(self, ipfsCtx, baseTopic, **kw):
        super(RSAEncryptedJSONPubsubService, self).__init__(
            ipfsCtx, baseTopic, peered=True, **kw)

    def config(self):
        base = super().config()
        return configMerge(base, cParentGet('serviceTypes.rsaEncJson'))

    @ipfsOp
    async def asyncMsgDataToJson(self, ipfsop, msg):
        try:
            dec = await ipfsop.rsaAgent.decrypt(
                base64.b64decode(msg['data']))
            return orjson.loads(dec.decode())
        except Exception as err:
            logger.debug(f'Could not decode encrypted message: {err}')
            return None

    async def peerEncFilter(self, piCtx, msg):
        return False

    async def peersToSend(self):
        # Yields (peerId, piCtx, aesSessionKey, topic)
        async with self.ipfsCtx.peers.lock.reader_lock:
            for peerId, piCtx in self.ipfsCtx.peers.byPeerId.items():
                yield (peerId, piCtx, None, None)

    @ipfsOp
    async def send(self, ipfsop, msg):
        async for peerId, piCtx, sessionKey, _topic in self.peersToSend():
            if await self.peerEncFilter(piCtx, msg) is True:
                continue

            topic = _topic if _topic else self.topic()

            pubKey = await piCtx.defaultRsaPubKey()

            if not pubKey:
                continue

            enc = await ipfsop.rsaAgent.encrypt(
                str(msg).encode(),
                pubKey,
                sessionKey=sessionKey,
                cacheKey=True
            )

            await ipfsop.sleep(0.05)

            if enc:
                await super().send(
                    base64.b64encode(enc).decode(),
                    topic=topic
                )

            await ipfsop.sleep(0.05)


class Curve25519JSONPubsubService(JSONPubsubService):
    encodingType = PS_ENCTYPE_CURVE25519
    hubKey = keyPsEncJson

    def __init__(self, ipfsCtx, baseTopic, privEccKey, **kw):
        self.__privEccKey = privEccKey
        self._authorizedPeers = []

        super(Curve25519JSONPubsubService, self).__init__(
            ipfsCtx, baseTopic, **kw)

    def config(self):
        base = super().config()
        return configMerge(base, cParentGet('serviceTypes.curve25519EncJson'))

    @ipfsOp
    async def getPrivEccKey(self, ipfsop):
        """
        Return the CURVE25519 priv key used for decoding
        """
        try:
            if self.__privEccKey:
                return self.__privEccKey
            else:
                # Default ECC key
                return ipfsop.curve25519Agent.privKey
        except Exception:
            return None

    @ipfsOp
    async def asyncMsgDataToJson(self, ipfsop, msg):
        try:
            sender = msg['from'] if isinstance(msg['from'], str) else \
                msg['from'].decode()

            if len(self._authorizedPeers) > 0 and \
               sender not in self._authorizedPeers:
                raise Exception(f'Unauthorized message from {sender} '
                                'on curve25519 topic {self.topic()}')

            # Load the peer context
            piCtx = ipfsop.ctx.peers.getByPeerId(sender)
            if not piCtx:
                raise Exception('Cannot find peer')

            # Get the peer's default curve25519 public key
            pubKey = await piCtx.defaultCurve25519PubKey()

            # curve25519 decryption
            dec = await ipfsop.ctx.curve25Exec.decrypt(
                base64.b64decode(msg['data']),
                await self.getPrivEccKey(),
                pubKey
            )

            if not dec:
                raise ValueError(
                    f'Curve25519 decryption failed : '
                    f'sender is: {sender}')

            return orjson.loads(dec.decode())
        except Exception as err:
            logger.debug(
                f'{self.topic()}: Could not decode encrypted message: {err}')
            return None

    async def peerEncFilter(self, piCtx, msg):
        return False

    async def peersToSend(self):
        raise Exception('implement peersToSend')

    @ipfsOp
    async def send(self, ipfsop, msg):
        """
        Send a message encrypted as curve25519 to all peers

        Implement peersToSend() as an async generator to tell which
        peers we should the message to.
        """
        try:
            pmfp = getattr(self, 'presetMessageForPeer')
        except Exception:
            usePmfp = False
        else:
            usePmfp = asyncio.iscoroutinefunction(pmfp)

        async for piCtx, sessionKey, _topic, pubKeyCid in self.peersToSend():
            if await self.peerEncFilter(piCtx, msg) is True:
                continue

            topic = _topic if _topic else self.topic()

            pubKey = await ipfsop.ctx.curve25Exec.pubKeyFromCid(
                pubKeyCid, timeout=5
            )

            if not pubKey:
                logger.debug(f'Could not get curve25519 public key for '
                             f'peer {piCtx.peerId} (CID: {pubKeyCid})')
                continue

            if usePmfp:
                msgString = await pmfp(piCtx, msg)
            else:
                msgString = str(msg)

            if not isinstance(msgString, str):
                continue

            enc = await ipfsop.ctx.curve25Exec.encrypt(
                msgString.encode(),
                await self.getPrivEccKey(),
                pubKey
            )

            await ipfsop.sleep(0.05)

            if enc:
                await super().send(
                    base64.b64encode(enc).decode(),
                    topic=topic
                )
            else:
                logger.debug(f'curve25519 encryption failed for '
                             f'peer {piCtx.peerId}')

            await ipfsop.sleep(0.05)
