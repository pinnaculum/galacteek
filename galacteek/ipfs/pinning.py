
import asyncio

import aioipfs

class Pinner(object):
    """ Pins objects on request through an async queue """

    def __init__(self, app, loop):
        self.pintasks = []
        self.app = app
        self.loop = loop
        self.queue = asyncio.Queue(loop=loop)
        self.lock = asyncio.Lock()
        self.pinstatus = {}

    def status(self):
        return self.pinstatus

    async def pin(self, path, recursive=False):
        ipfsClient = self.app.getIpfsClient()
        self.pinstatus[path] = None
        async for pinned in ipfsClient.pin.add(path, recursive=recursive):
            await asyncio.sleep(0)
            async with self.lock:
                self.pinstatus[path] = pinned
        async with self.lock:
            del self.pinstatus[path]
        return path

    async def process(self):
        while True:
            item = await self.queue.get()
            if item is None:
                break
            path, recursive, callback = item
            f = asyncio.ensure_future(self.pin(path, recursive=recursive))
            if callback:
                f.add_done_callback(callback)
