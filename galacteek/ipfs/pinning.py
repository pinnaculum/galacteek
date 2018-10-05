
import asyncio

import aioipfs

from galacteek import log
from galacteek.ipfs.wrappers import ipfsOp

class Pinner(object):
    """ Pins objects on request through an async queue """

    def __init__(self, ctx):
        self._pinQueue = asyncio.Queue()
        self._ctx = ctx
        self.lock = asyncio.Lock()
        self._pinStatus = {}

    @property
    def pinQueue(self):
        return self._pinQueue

    @property
    def ipfsCtx(self):
        return self._ctx

    @property
    def status(self):
        return self._pinStatus

    def debug(self, msg):
        log.debug('Pinning service: {}'.format(msg))

    def _emitSLength(self):
        self.ipfsCtx.pinItemsCount.emit(len(self._pinStatus))

    def pathRegister(self, path):
        self._pinStatus[path] = {}
        self.ipfsCtx.pinNewItem.emit(path)
        self._emitSLength()

    def pathDelete(self, path):
        if path in self._pinStatus:
            del self._pinStatus[path]
        self._emitSLength()

    @ipfsOp
    async def pin(self, op, path, recursive=False):
        self.debug('pinning object {0}, recursive is {1}'.format(
            path, recursive))
        self.pathRegister(path)

        try:
            async for pinned in op.client.pin.add(path, recursive=recursive):
                self.debug('Pinning progress {0}: {1}'.format(path, pinned))
                await asyncio.sleep(0)
                with await self.lock:
                    self._pinStatus[path] = pinned
                self.ipfsCtx.pinItemStatusChanged.emit(path, pinned)
        except aioipfs.APIError as err:
            self.debug('Pinning error {0}: {1}'.format(path, str(err.message)))

        with await self.lock:
            self.pathDelete(path)

        self.ipfsCtx.pinFinished.emit(path)
        return path

    async def queue(self, path, recursive, onSuccess):
        """ Queue an item for processing """
        await self.pinQueue.put((path, recursive, onSuccess))
        self.ipfsCtx.pinQueueSizeChanged.emit(self.pinQueue.qsize())

    async def process(self):
        try:
            while True:
                item = await self.pinQueue.get()
                if item is None:
                    self.debug('null item in queue')
                    continue

                self.ipfsCtx.pinQueueSizeChanged.emit(self.pinQueue.qsize())
                path, recursive, callback = item
                f = asyncio.ensure_future(self.pin(path, recursive=recursive))
                if callback:
                    f.add_done_callback(callback)
        except asyncio.CancelledError as err:
            self.debug('cancelled error: {}'.format(str(err)))
