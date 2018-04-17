
import sys
import json

import aioipfs
import asyncio

from galacteek.ipfs.pubsubmsg import MarksBroadcastMessage

class PubsubListener(object):
    """ IPFS pubsub listener for a given topic """

    def __init__(self, client, loop, ipfsCtx, topic='defaulttopic'):
        self.ipfsCtx = ipfsCtx
        self.loop = loop
        self.topic = topic
        self.client = client
        self.inqueue = asyncio.Queue()
        self.lock = asyncio.Lock()

        self.tsServe = None
        self.tsProcess = None
        self.tsPeriodic = None

    def msgDataJson(self, msg):
        """
        Decode JSON data contained in a pubsub message
        """
        try:
            return json.loads(msg['data'].decode())
        except Exception as e:
            print('Could not decode {}'.format(
                msg['data'], file=sys.stderr))
            return None

    def start(self):
        self.tsServe = self.loop.create_task(self.serve(self.client))
        self.tsProcess = self.loop.create_task(self.processMessages())
        self.tsPeriodic = self.loop.create_task(self.periodic())

    def stop(self):
        for ts in [ self.tsServe, self.tsProcess, self.tsPeriodic ]:
            if ts: ts.cancel()

    async def processMessages(self):
        return True

    async def periodic(self):
        return True

    async def serve(self, client):
        nodeInfo = await client.core.id()
        nodeId = nodeInfo['ID']

        async with client as cli:
            async for message in cli.pubsub.sub(self.topic):
                await asyncio.sleep(0)
                if message['from'] == nodeId:
                    continue

                self.ipfsCtx.pubsubMessageRx.emit()
                await self.inqueue.put(message)

    async def send(self, data, topic=None):
        if topic is None:
            topic = self.topic
        status = await self.client.pubsub.pub(topic, data)
        self.ipfsCtx.pubsubMessageTx.emit()
        return status

class BookmarksExchanger(PubsubListener):
    def __init__(self, client, loop, ipfsCtx, marksLocal, marksNetwork):
        super().__init__(client, loop, ipfsCtx, topic='galacteek.marks')
        self.marksLocal = marksLocal
        self.marksNetwork = marksNetwork

    async def periodic(self):
        """ Very basic broadcasting of marks for now """
        while True:
            await asyncio.sleep(60)
            o = self.marksLocal.getAll(share=True)
            if len(o.keys()) == 0:
                continue
            msg = MarksBroadcastMessage.make(o)
            await self.send(str(msg))

    async def processMessages(self):
        while True:
            data = await self.inqueue.get()

            msg = self.msgDataJson(data)
            if not msg:
                continue

            msgType = msg.get('msgtype', None)
            if msgType == MarksBroadcastMessage.TYPE:
                await self.processBroadcast(msg)

            await asyncio.sleep(0)

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
            self.marksNetwork.insertMark(mark, 'auto')
            addedCount += 1

        if addedCount > 0:
            self.ipfsCtx.pubsubMarksReceived.emit(addedCount)
