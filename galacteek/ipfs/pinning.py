
import asyncio

import aioipfs

class Pinner(object):
    """ Pins objects on request through an async queue """

    def __init__(self, app):
        self.pintasks = []
        self.app = app
        self.queue = asyncio.Queue(loop=self.app.loop)
        self.lock = asyncio.Lock()
        self.pinstatus = {}

    def status(self):
        return self.pinstatus

    def _emitSLength(self):
        self.app.ipfsCtx.pinItemsCount.emit(len(self.pinstatus))

    def pathRegister(self, path):
        self.pinstatus[path] = {}
        self.app.ipfsCtx.pinNewItem.emit(path)
        self._emitSLength()

    def pathDelete(self, path):
        if path in self.pinstatus:
            del self.pinstatus[path]
        self._emitSLength()

    async def pin(self, path, recursive=False):
        ipfsClient = self.app.ipfsClient
        self.pathRegister(path)

        async for pinned in ipfsClient.pin.add(path, recursive=recursive):
            await asyncio.sleep(0)
            async with self.lock:
                self.pinstatus[path] = pinned
            self.app.ipfsCtx.pinItemStatusChanged.emit(path, pinned)

        async with self.lock:
            self.pathDelete(path)

        self.app.ipfsCtx.pinFinished.emit(path)
        return path

    async def enqueue(self, path, recursive, onSuccess):
        await self.queue.put((path, recursive, onSuccess))
        self.app.ipfsCtx.pinQueueSizeChanged.emit(self.queue.qsize())

    async def process(self):
        while True:
            item = await self.queue.get()
            if item is None:
                continue
            self.app.ipfsCtx.pinQueueSizeChanged.emit(self.queue.qsize())
            path, recursive, callback = item
            f = asyncio.ensure_future(self.pin(path, recursive=recursive))
            if callback:
                f.add_done_callback(callback)
