
import asyncio
import time

from PyQt5.QtCore import (pyqtSignal, QObject)

from galacteek import log, ensure, asyncify
from galacteek.ipfs.wrappers import ipfsOp
from galacteek.core.jtraverse import traverseParser

class MutableIPFSJson(QObject):
    """
    Mutable IPFS JSON object.

    As you make changes to the JSON object contained within this object, a copy
    of that JSON is maintained in the MFS at the given path

    Signals:
        changed: emit this signal when you changed the object and it will
            trigger saving
        entryChanged: emitted when the object has been flushed to IPFS and is
            represented by a new hash
        available: object has been loaded (emitted once on init)

    :param str mfsFilePath: the path inside the MFS for this object
    """

    changed = pyqtSignal()
    entryChanged = pyqtSignal()
    available = pyqtSignal(dict)

    def __init__(self, mfsFilePath,  **kw):
        super().__init__()

        self.lock = asyncio.Lock()
        self.loaded = asyncio.Future()
        self.evLoaded = asyncio.Event()
        self._root = None
        self._avail = False
        self._curEntry = None
        self._entryHistory = []
        self._mfsFilePath = mfsFilePath
        self.__dict__.update(kw)

        self.changed.connect(self.onChanged)
        self.available.connect(self.onObjAvailable)

    def debug(self, msg):
        log.debug('MFS JSON {0}: {1}'.format(self.mfsFilePath, msg))

    def onObjAvailable(self, r):
        self._avail = True

    def onChanged(self):
        self.save()

    def initObj(self):
        raise Exception('implement initObj')

    @property
    def mfsFilePath(self):
        return self._mfsFilePath # path inside the mfs

    @property
    def curEntry(self):
        """
        The current IPFS entry representing this object
        """
        return self._curEntry

    @property
    def avail(self):
        return self._avail

    @curEntry.setter
    def curEntry(self, value):
        self._entryHistory.append((time.time(), value))
        self._curEntry = value
        self.entryChanged.emit()

    @property
    def root(self):
        return self._root

    async def load(self):
        await self.loadIpfsObj()

    @ipfsOp
    async def loadIpfsObj(self, op):
        """
        Load the JSON from the MFS if it already exists or initialize a new
        object otherwise
        """
        self.debug('Loading mutable object from {}'.format(self.mfsFilePath))

        obj = await op.filesReadJsonObject(self.mfsFilePath)

        if obj:
            self.debug('Successfully loaded JSON')
            self._root = obj
            self.curEntry = await op.filesStat(self.mfsFilePath)
            self.loaded.set_result(True)
            self.evLoaded.set()
        else:
            self.debug('JSON empty or invalid, initializing')
            self._root = self.initObj()
            await self.ipfsSave()
            self.loaded.set_result(True)
            self.evLoaded.set()

        self.parser = traverseParser(self.root)
        if self.upgrade() is True:
            await self.ipfsSave()

        self.available.emit(self.root)

    @asyncify
    async def save(self):
        await self.ipfsSave()

    @ipfsOp
    async def ipfsSave(self, op):
        with await self.lock:
            resp = await op.filesWriteJsonObject(self.mfsFilePath, self.root)

            if resp is not None:
                self.curEntry = await op.filesStat(self.mfsFilePath)
                return True
            else:
                return False

    def upgrade(self):
        return False
