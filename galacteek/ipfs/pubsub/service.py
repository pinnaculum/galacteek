
import sys
import json

import aioipfs
import asyncio
import datetime

from galacteek import log as logger

from galacteek.ipfs.pubsub.messages import (MarksBroadcastMessage,
        PeerIdentMessageV1, PeerLogoutMessage)
from galacteek.ipfs.wrappers import *
from galacteek.ipfs.ipfsops import IPFSOperator
from galacteek.core.asynclib import asyncify

class PubsubService(object):
    """
    Generic IPFS pubsub service
    """

    def __init__(self, ipfsCtx, client, topic='galacteek.default',
            runPeriodic=False):
        self.client = client
        self.ipfsCtx = ipfsCtx
        self.topic = topic
        self.inQueue = asyncio.Queue()
        self.errorsQueue = asyncio.Queue()
        self.lock = asyncio.Lock()

        self._receivedCount = 0
        self._errorsCount = 0
        self._runPeriodic = runPeriodic

        self.tskServe = None
        self.tskProcess = None
        self.tskPeriodic = None

    @property
    def receivedCount(self):
        return self._receivedCount

    @property
    def errorsCount(self):
        return self._errorsCount

    @property
    def runPeriodic(self):
        return self._runPeriodic

    def debug(self, msg):
        logger.debug('PS[{0}]: {1}'.format(self.topic, msg))

    def logStatus(self):
        self.debug('** Messages received: {0}, errors: {1}'.format(
             self.receivedCount, self.errorsCount))

    def start(self):
        """ Create the different tasks for this service """
        self.tskServe = self.ipfsCtx.loop.create_task(self.serve())
        self.tskProcess = self.ipfsCtx.loop.create_task(self.processMessages())

        if self.runPeriodic:
            self.tskPeriodic = self.ipfsCtx.loop.create_task(self.periodic())

    async def stop(self):
        await self.shutdown()
        for tsk in [ self.tskServe, self.tskProcess, self.tskPeriodic ]:
            if not tsk:
                continue

            tsk.cancel()
            try:
                await tsk
            except asyncio.CancelledError as err:
                continue
            else:
                self.debug('task {}: shutdown ok'.format(tsk))

    async def shutdown(self):
        pass

    async def processMessages(self):
        """ Messages processing task to be implemented in your listener """
        return True

    async def periodic(self):
        return True

    async def serve(self):
        """
        Subscribe to the pubsub topic, read and filter incoming messages
        (dropping the ones emitted by us). Selected messages are put on the
        async queue (inQueue) to be later treated in the processMessages() task
        """

        nodeId = self.ipfsCtx.node.id

        try:
            async for message in self.client.pubsub.sub(self.topic):
                if message['from'].decode() == nodeId:
                    continue

                self.ipfsCtx.pubsub.psMessageRx.emit()

                await self.inQueue.put(message)
                self._receivedCount += 1
                await asyncio.sleep(0)
        except asyncio.CancelledError as e:
            self.debug('Cancelled, queue size was {0}'.format(
                self.inQueue.qsize()))
            return
        except Exception as e:
            self.debug('Serve interrupted by unknown exception {}'.format(
                str(e)))

    async def send(self, data, topic=None):
        """
        Publish a message

        :param str data: message payload
        """

        if topic is None:
            topic = self.topic

        status = await self.client.pubsub.pub(topic, data)
        self.ipfsCtx.pubsub.psMessageTx.emit()
        return status

class JSONPubsubService(PubsubService):
    """
    JSON pubsub listener, handling incoming messages as JSON objects
    """

    def msgDataToJson(self, msg):
        """
        Decode JSON data contained in a pubsub message
        """
        try:
            return json.loads(msg['data'].decode())
        except Exception as e:
            logger.debug('Could not decode JSON message data')
            return None

    async def processMessages(self):
        try:
            while True:
                data = await self.inQueue.get()

                if data is None:
                    break

                msg = self.msgDataToJson(data)
                if msg is None:
                    continue

                logger.debug('Received Pubsub message {}'.format(
                    json.dumps(msg, indent=4)))

                try:
                    await self.processJsonMessage(data['from'].decode(), msg)
                except Exception as exc:
                    logger.debug(
                            'processJsonMessage error: {}'.format(str(exc)))
                    await self.errorsQueue.put((msg, exc))
                    self._errorsCount += 1
        except asyncio.CancelledError as e:
            return
        except Exception as e:
            return

    async def processJsonMessage(self, sender, msg):
        """ Implement this method to process incoming JSON messages"""
        return True

class PSHashmarksExchanger(JSONPubsubService):
    def __init__(self, ipfsCtx, client, marksLocal, marksNetwork):
        super().__init__(ipfsCtx, client, topic='galacteek.ipfsmarks')

        self.marksLocal = marksLocal
        self.marksNetwork = marksNetwork
        self.marksLocal.markAdded.connect(self.onMarkAdded)

    @asyncify
    async def onMarkAdded(self, path, mark):
        if mark['share'] is True:
            await self.broadcastMarks({path: mark})

    async def broadcastMarks(self, marks):
        msg = MarksBroadcastMessage.make(marks)
        await self.send(str(msg))

    async def broadcastAllSharedMarks(self):
        all = self.marksLocal.getAll(share=True)
        if len(all.keys()) == 0:
            return
        msg = MarksBroadcastMessage.make(all)
        await self.send(str(msg))

    async def processJsonMessage(self, sender, msg):
        msgType = msg.get('msgtype', None)
        if msgType == MarksBroadcastMessage.TYPE:
            await self.processBroadcast(msg)

    async def processBroadcast(self, msg):
        marks = msg.get('marks', None)
        if not marks:
            return

        addedCount = 0
        for mark in marks.items():
            await asyncio.sleep(0)

            mPath = mark[0]
            if self.marksNetwork.search(mPath):
                continue

            category = 'auto'
            tsCreated = mark[1].get('tscreated', None)

            if tsCreated:
                date = datetime.datetime.fromtimestamp(tsCreated)
                category = '{0}/{1}/{2}'.format(date.year, date.month,
                        date.day)

            self.marksNetwork.insertMark(mark, category)
            addedCount += 1

        if addedCount > 0:
            with await self.lock:
                await self.marksNetwork.saveAsync()

            self.ipfsCtx.pubsubMarksReceived.emit(addedCount)

class PSMainService(JSONPubsubService):
    def __init__(self, ipfsCtx, client):
        super().__init__(ipfsCtx, client, topic='galacteek.main')

class PSPeersService(JSONPubsubService):
    def __init__(self, ipfsCtx, client):
        super().__init__(ipfsCtx, client, topic='galacteek.peers',
                runPeriodic=True)

        self._curProfile = None
        self._identEvery = 45
        self.ipfsCtx.profileChanged.connect(self.onProfileChanged)

    @property
    def curProfile(self):
        return self.ipfsCtx.currentProfile

    @property
    def identEvery(self):
        return self._identEvery

    @asyncify
    async def onProfileChanged(self, pName, profile):
        await profile.userInfo.loaded

        try:
            profile.userInfo.entryChanged.disconnect(self.userInfoChanged)
            profile.userInfo.available.disconnect(self.userInfoAvail)
        except Exception as e:
            pass

        self.curProfile.userInfo.entryChanged.connect(self.userInfoChanged)
        self.curProfile.userInfo.available.connect(self.userInfoAvail)
        await self.sendIdent(self.curProfile)

    @asyncify
    async def userInfoAvail(self, arg):
        await self.sendIdent(self.curProfile)

    @asyncify
    async def userInfoChanged(self):
        with await self.lock:
            await self.sendIdent(self.curProfile)

    @ipfsOp
    async def sendIdent(self, op, profile):
        nodeId = op.ctx.node.id
        uInfo = profile.userInfo

        if not uInfo.valid():
            return

        if uInfo.schemaVersion is 1:
            msg = PeerIdentMessageV1.make(nodeId, uInfo.objHash,
                    uInfo.root, profile.dagUser.dagCid,
                    profile.keyRootId, self.ipfsCtx.p2p.servicesFormatted())

            await self.send(str(msg))

    async def processJsonMessage(self, sender, msg):
        msgType = msg.get('msgtype', None)

        if msgType == PeerIdentMessageV1.TYPE:
            await self.handleIdentMessageV1(sender, msg)
        elif msgType == PeerLogoutMessage.TYPE:
            await self.handleLogoutMessage(sender, msg)

        await asyncio.sleep(0)

    async def handleLogoutMessage(self, sender, msg):
        lMsg = PeerLogoutMessage(msg)
        await self.ipfsCtx.peers.unregister(sender)

    async def handleIdentMessageV1(self, sender, msg):
        iMsg = PeerIdentMessageV1(msg)
        if not iMsg.valid():
            return

        if sender != iMsg.peer:
            # You forging pubsub messages, son ?
            return

        await self.ipfsCtx.peers.registerFromIdent(iMsg)

    @ipfsOp
    async def shutdown(self, op):
        msg = PeerLogoutMessage.make(op.ctx.node.id)
        await self.send(str(msg))

    async def periodic(self):
        while True:
            await asyncio.sleep(self.identEvery)

            with await self.lock:
                if self.curProfile:
                    await self.sendIdent(self.curProfile)

__all__ = [
        'PubsubService',
        'PSHashmarksExchanger',
        'PSMainService',
        'PSPeersService'
]
