import asyncio
import os.path

from async_generator import async_generator, yield_, yield_from_

from PyQt5.QtCore import (pyqtSignal, QObject)

from galacteek import log
from galacteek.ipfs.wrappers import ipfsOp
from galacteek.ipfs.cidhelpers import joinIpfs
from galacteek.ipfs.ipfsops import *  # noqa
from galacteek.ipfs import pb
from galacteek.core.asynclib import async_enterable
from galacteek.core.jtraverse import traverseParser


class DAGObj:
    def __init__(self, data):
        self.data = data


class DAGQuery(object):
    def __init__(self, dagCid=None, dagRoot=None):
        self._dagCid = dagCid
        self._dagRoot = dagRoot
        self.evLoaded = asyncio.Event()

    def debug(self, msg):
        log.debug('DAG query: {}'.format(msg))

    @property
    def dagCid(self):
        return self._dagCid

    @property
    def dagRoot(self):
        return self._dagRoot

    def path(self, subpath):
        return os.path.join(joinIpfs(self.dagCid), subpath)

    async def waitLoaded(self, timeout=15):
        return asyncio.wait_for(self.evLoaded.wait(), timeout)

    @ipfsOp
    async def load(self, op, timeout=10):
        self._dagRoot = await op.waitFor(op.dagGet(self.dagCid), timeout)
        if self.dagRoot:
            self.evLoaded.set()
            return self.dagRoot

    @ipfsOp
    async def get(self, op, path):
        dagNode = await op.dagGet(
            os.path.join(self.dagCid, path))

        if isinstance(dagNode, dict) and 'data' in dagNode and \
                'links' in dagNode:
            """ Try and decode the protobuf data """
            msg = pb.decodeDagNode(dagNode['data'])
            if not msg:
                return
            return msg['data']
        else:
            return dagNode

    @ipfsOp
    async def cat(self, op, path):
        return await op.client.cat(
            os.path.join(self.dagCid, path))

    @ipfsOp
    async def list(self, op, path=''):
        data = await self.get(path)
        if data is None:
            return

        if isinstance(data, dict):
            return data.keys()

    @ipfsOp
    async def resolve(self, op, path=''):
        return await op.dagResolve(
            os.path.join(self.dagCid, path))

    @async_generator
    async def walk(self, op, path='', maxObjSize=0, depth=1):
        """
        Do not use this!
        """

        data = await self.get(path)
        if data is None:
            return

        if isinstance(data, bytes):
            """ Protobuf data decoded by get() """
            await yield_((path, DAGObj(data)))

        elif isinstance(data, dict):
            for objKey, objValue in data.items():
                if objKey == '/':
                    out = await op.client.cat(objValue)
                    await yield_((path, DAGObj(out)))
                if objKey == 'data' or objKey == 'links':
                    continue
                else:
                    await yield_from_(
                        self.walk(op, path=os.path.join(path, objKey),
                                  maxObjSize=maxObjSize, depth=depth)
                    )

        elif isinstance(data, list):
            for idx, obj in enumerate(data):
                await yield_from_(
                    self.walk(op, path=os.path.join(path, str(idx)),
                              maxObjSize=maxObjSize)
                )
        elif isinstance(data, str):
            await yield_((path, DAGObj(data)))

    async def __aenter__(self):
        if self.dagRoot is None:
            await self.load()
            if self.dagRoot is None:
                raise Exception('Cannot load dag')
        return self

    async def __aexit__(self, *args):
        pass


class EvolvingDAG(QObject):
    """
    :param str dagMetaMfsPath: the path inside the MFS for the metadata
        describing this DAG
    """

    changed = pyqtSignal()
    metadataEntryChanged = pyqtSignal()
    available = pyqtSignal(object)

    keyCidLatest = 'cidlatest'

    def __init__(self, dagMetaMfsPath, dagMetaHistoryMax=12, loop=None):
        super().__init__()

        self.lock = asyncio.Lock()
        self.loop = loop if loop else asyncio.get_event_loop()
        self.loaded = asyncio.Future()

        self._curMetaEntry = None
        self._dagRoot = None
        self._dagMeta = None
        self._dagCid = None
        self._dagMetaMaxHistoryItems = dagMetaHistoryMax
        self._dagMetaMfsPath = dagMetaMfsPath

    @property
    def dagMetaMfsPath(self):
        return self._dagMetaMfsPath  # path inside the mfs

    @property
    def dagMetaMaxHistoryItems(self):
        return self._dagMetaMaxHistoryItems

    @property
    def curMetaEntry(self):
        return self._curMetaEntry

    @curMetaEntry.setter
    def curMetaEntry(self, value):
        self._curMetaEntry = value

    @property
    def dagCid(self):
        return self._dagCid

    @dagCid.setter
    def dagCid(self, cid):
        self._dagMeta[self.keyCidLatest] = cid
        self._dagCid = cid
        self.debug("DAG's CID now is {0}".format(cid))

    @property
    def dagMeta(self):
        return self._dagMeta

    @property
    def dagRoot(self):
        return self._dagRoot

    @property
    def root(self):
        return self._dagRoot

    def debug(self, msg):
        log.debug('EDAG ({meta}): {msg}'.format(
            meta=self.dagMetaMfsPath, msg=msg))

    def initDag(self):
        return {}

    def mkLink(self, cid):
        if isinstance(cid, str):
            return {"/": cid}
        elif isinstance(cid, dict):
            # assume it's a dict which has a 'Hash' key
            return {"/": cid['Hash']}

    async def load(self):
        await self.loadDag()

    @ipfsOp
    async def loadDag(self, op):
        self.debug('Loading DAG metadata file')
        meta = await op.filesReadJsonObject(self.dagMetaMfsPath)

        self.debug('Metadata is {}'.format(meta))
        if meta is not None:
            self._dagMeta = meta
            latest = self.dagMeta.get(self.keyCidLatest, None)
            if latest:
                self.dagCid = latest
                self.debug('Getting DAG: {cid}'.format(cid=self.dagCid))
                self._dagRoot = await op.dagGet(self.dagCid)
            else:
                self.debug('No CID history, reinitializing')
                # How inconvenient ..
                # TODO: the history could be used here to recreate a DAG
                # from previous CIDs but we really shouldn't have to enter here
                self._dagRoot = {}

            self.loaded.set_result(True)
        else:
            self._dagMeta = {
                self.keyCidLatest: None,
                'history': []
            }
            self._dagRoot = self.initDag()
            await self.ipfsSave()
            self.loaded.set_result(True)

        self.parser = traverseParser(self.dagRoot)
        self.loop.call_soon(self.available.emit, self.dagRoot)

    @ipfsOp
    async def ipfsSave(self, op):
        self.debug('Saving (acquiring lock)')
        with await self.lock:
            prevCid = self.dagCid
            history = self.dagMeta.setdefault('history', [])
            maxItems = self.dagMetaMaxHistoryItems

            # We always PIN the latest DAG and do a pin update using the
            # previous item in the history

            cid = await op.dagPut(self.dagRoot, pin=True)
            if cid is not None:
                if prevCid is not None and prevCid not in history:
                    if len(history) > maxItems:
                        # Purge old items
                        [history.pop() for idx in range(
                            0, len(history) - maxItems)]

                    history.insert(0, prevCid)
                    await op.pinUpdate(prevCid, cid)

                # Save the new CID and update the metadata
                self.dagCid = cid
                await op.filesWriteJsonObject(self.dagMetaMfsPath,
                                              self.dagMeta)
                entry = await op.filesStat(self.dagMetaMfsPath)
                if entry:
                    self.curMetaEntry = entry
            else:
                # Bummer
                self.debug('DAG could not be built')
                return False

        return True

    @ipfsOp
    async def get(self, op, path):
        self.debug('DAG get {}'.format(os.path.join(self.dagCid, path)))
        dagNode = await op.dagGet(
            os.path.join(self.dagCid, path))

        if isinstance(dagNode, dict) and 'data' in dagNode and \
                'links' in dagNode:
            """ Try and decode the protobuf data """
            msg = pb.decodeDagNode(dagNode['data'])
            if not msg:
                return
            return msg['data']
        else:
            return dagNode

    @ipfsOp
    async def cat(self, op, path):
        return await op.client.cat(
            os.path.join(self.dagCid, path))

    @ipfsOp
    async def list(self, op, path=''):
        data = await self.get(path)
        if data is None:
            return

        if isinstance(data, dict):
            return data.keys()

    @ipfsOp
    async def resolve(self, op, path=''):
        return await op.dagResolve(
            os.path.join(self.dagCid, path))

    @async_generator
    async def walk(self, op, path='', maxObjSize=0, depth=1):
        """
        Do not use this!
        """

        data = await self.get(path)
        if data is None:
            return

        if isinstance(data, dict) and 'data' in data and 'links' in data:
            """ Try and decode the protobuf data """
            msg = pb.decodeDagNode(data['data'])
            if not msg:
                return
            if maxObjSize == 0 or \
                    (maxObjSize > 0 and msg['size'] < maxObjSize):
                await yield_((path, DAGObj(msg['data'])))

        if not data:
            return

        if isinstance(data, dict):
            for objKey, objValue in data.items():
                if objKey == '/':
                    out = await op.client.cat(objValue)
                    await yield_((path, DAGObj(out)))
                if objKey == 'data' or objKey == 'links':
                    continue
                else:
                    await yield_from_(
                        self.walk(op, path=os.path.join(path, objKey),
                                  maxObjSize=maxObjSize, depth=depth)
                    )

        elif isinstance(data, list):
            for idx, obj in enumerate(data):
                await yield_from_(
                    self.walk(op, path=os.path.join(path, str(idx)),
                              maxObjSize=maxObjSize)
                )
        elif isinstance(data, str):
            await yield_((path, DAGObj(data)))

    async def __aenter__(self):
        """
        Lock is acquired on entering the async ctx manager
        """
        await self.lock.acquire()
        return self

    async def __aexit__(self, *args):
        """
        Release the lock and save. The changed signal is emitted
        """
        self.lock.release()
        self.loop.call_soon(self.changed.emit)

    @async_enterable
    async def query(self):
        return DAGQuery(dagCid=self.dagCid, dagRoot=self.dagRoot)
