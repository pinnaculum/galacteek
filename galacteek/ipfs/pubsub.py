
import sys

import aioipfs
import asyncio

class PubsubListener(object):
    def __init__(self, client, loop=None, topic='defaulttopic'):
        self.loop = loop
        self.topic = topic
        self.client = client
        self.inqueue = asyncio.Queue()

    def start(self):
        self.loop.create_task(self.serve(self.client))

    async def serve(self, client):
        nodeInfo = await client.core.id()
        nodeId = nodeInfo['ID']

        async with client as cli:
            async for message in cli.pubsub.sub(self.topic):
                await asyncio.sleep(0)
                if message['from'] == nodeId:
                    continue

                self.inqueue.put(message)
