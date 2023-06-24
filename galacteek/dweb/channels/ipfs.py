from pathlib import Path
import shutil
import tempfile
import traceback
import io
import zipfile

from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import pyqtProperty
from PyQt5.QtCore import QVariant
from PyQt5.QtCore import QByteArray
from PyQt5.QtCore import QJsonValue
from PyQt5.QtCore import QUrl
from PyQt5.QtCore import QObject

from galacteek import log
from galacteek import ensure
from galacteek.core import runningApp
from galacteek.core.ps import KeyListener

from galacteek.ipfs.mimetype import detectMimeType
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ipfs.pubsub.messages import PubsubMessage
from galacteek.ipfs.pubsub.service import JSONPubsubService
from galacteek.ipfs.pubsub.service import Curve25519JSONPubsubService
from galacteek import ensureSafe

from . import GAsyncObject
from . import opSlot
from . import tcSlot


class IPFSInterface(object):
    async def a_addFromPath(self, ipfsop, path, opts):
        fp = Path(path)

        if not fp.exists():
            # Try QUrl for file://
            url = QUrl(path)

            if url.isValid() and url.scheme() == 'file':
                fp = Path(url.toLocalFile())

        if not fp.exists():
            log.info(f'Cannot find file from path: {fp}')
            return {}

        entry = await ipfsop.addPath(
            str(fp),
            callback=opts.get('callback', None),
            recursive=opts.get('recursive', True),
            only_hash=opts.get('only_hash', False),
            pin=opts.get('pin', True),
            wrap=opts.get('wrap', False)
        )

        if entry:
            return entry

        return {}

    async def a_psJsonSend_Old(self, app, loop, topic, msg):
        ipfsop = app.getIpfsOperator()

        service = ipfsop.ctx.pubsub.byTopic(topic)

        if service:
            await service.send(PubsubMessage(msg))
            return True

        return False

    async def a_psJsonSend(self, app, loop, topic, msg):
        ipfsop = app.getIpfsOperator()

        service = ipfsop.ctx.pubsub.byTopic(topic)

        if service:
            await service.send(PubsubMessage(msg))
            return True

        return False

    async def a_streamRequest(self, app, loop,
                              peerId,
                              protocol,
                              path,
                              body):
        ipfsop = app.ipfsOperatorForLoop(loop)

        p2pEndpoint = f'/p2p/{peerId}{protocol}'

        try:
            async with ipfsop.p2pDialerFromAddr(
                    p2pEndpoint,
                    allowLoopback=True) as dial:
                async with dial.session as session:
                    async with session.get(
                            dial.httpUrl(path)) as resp:
                        if resp.status != 200:
                            raise Exception(f'error: code {resp.status}')

                        resp = await resp.json()

                        assert isinstance(resp, dict)

                        return QVariant(resp)
        except Exception as err:
            log.debug(f'{p2pEndpoint}: request error: {err}')

            return QVariant({})


class IPFSHandler(GAsyncObject, IPFSInterface, KeyListener):
    psJsonRx = pyqtSignal(str, str, QVariant)
    fileAdded = pyqtSignal(str, str)

    async def addFileCallback(self, entry):
        self.fileAdded.emit(entry['Name'], entry['Hash'])

    async def event_g_pubsub_json(self, key, message):
        try:
            # unpack
            sender, topic, msg = message

            self.psJsonRx.emit(sender, topic, QVariant(msg))
        except Exception:
            pass

    @opSlot(str, QJsonValue)
    async def add(self, path, options):
        ipfsop = self.app.ipfsOperatorForLoop()

        opts = self._dict(options)
        opts['callback'] = self.addFileCallback

        return await self.a_addFromPath(ipfsop, path, opts)

    async def __addString(self, data):
        ipfsop = self.app.ipfsOperatorForLoop()

        try:
            entry = await ipfsop.addString(data)
            assert entry is not None
        except Exception:
            return {}
        else:
            return entry

    @opSlot(str)
    async def addStr(self, data):
        return await self.__addString(data)

    @tcSlot(str)
    async def addStrSync(self, data):
        return await self.__addString(data)

    async def __addBytes(self, data):
        ipfsop = self.app.ipfsOperatorForLoop()

        try:
            entry = await ipfsop.addBytes(bytes(data))
            assert entry is not None
        except Exception:
            return {}
        else:
            return entry

    @opSlot(QByteArray)
    async def addBytes(self, data):
        return await self.__addBytes(data)

    @tcSlot(QByteArray)
    async def addBytesSync(self, data):
        return await self.__addBytes(data)

    @tcSlot(QJsonValue)
    async def addJson(self, obj):
        ipfsop = self.app.ipfsOperatorForLoop()

        try:
            entry = await ipfsop.addJson(self._dict(obj))
            assert entry is not None
        except Exception:
            traceback.print_exc()
            return {}
        else:
            return entry

    @opSlot(str, QJsonValue)
    async def cat(self, path, options):
        opts = self._dict(options)
        offset = opts.get('offset', None)
        length = opts.get('length', None)
        timeout = opts.get('timeout', None)

        try:
            data = await (self.app.ipfsOperatorForLoop()).catObject(
                path,
                offset=offset,
                length=length,
                timeout=timeout
            )
            assert data is not None
        except Exception:
            return QVariant(QByteArray(bytes(b'')))
        else:
            return QVariant(QByteArray(bytes(data)))

    @opSlot(str, str)
    async def filesCp(self, src: str, dest: str):
        try:
            return await (self.app.ipfsOperatorForLoop()).filesCp(
                src, dest
            )
        except Exception:
            return False

    @opSlot(QJsonValue, str, str)
    async def filesLink(self, entry: QJsonValue, dest: str, name: str):
        try:
            return await (self.app.ipfsOperatorForLoop()).filesLink(
                self._dict(entry),
                dest,
                name=name if name else None
            )
        except Exception:
            traceback.print_exc()
            return False

    @opSlot(QJsonValue, str)
    async def filesLinkFp(self, entry: QJsonValue, dest: str):
        try:
            return await (self.app.ipfsOperatorForLoop()).filesLinkFp(
                self._dict(entry),
                dest
            )
        except Exception:
            traceback.print_exc()
            return False

    @opSlot(str, str, bool)
    async def filesDelete(self, path: str, name: str, recursive: bool):
        try:
            return await (self.app.ipfsOperatorForLoop()).filesDelete(
                path, name, recursive=recursive
            )
        except Exception:
            traceback.print_exc()
            return False

    @opSlot(str, bool)
    async def filesMkdir(self, path: str, parents: bool):
        try:
            return await (self.app.ipfsOperatorForLoop()).filesMkdir(
                path, parents=parents
            )
        except Exception:
            traceback.print_exc()
            return False

    @opSlot(str, str)
    async def filesMove(self, src: str, dst: str):
        try:
            return await (self.app.ipfsOperatorForLoop()).filesMove(src, dst)
        except Exception:
            traceback.print_exc()
            return False

    @opSlot(str, bool)
    async def filesList(self, path: str, sort: bool):
        try:
            return await (self.app.ipfsOperatorForLoop()).filesList(
                path, sort=sort
            )
        except Exception:
            traceback.print_exc()
            return False

    @opSlot(str, bytes, int, int, bool, bool)
    async def filesWrite(self, path: str, data: bytes,
                         offset: int,
                         count: int,
                         create: bool,
                         truncate: bool):
        try:
            return await (self.app.ipfsOperatorForLoop()).filesWrite(
                path, data,
                create=create,
                truncate=truncate,
                offset=offset,
                count=count
            )
        except Exception:
            traceback.print_exc()
            return False

    @opSlot(str)
    async def getJson(self, path):
        ipfsop = self.app.ipfsOperatorForLoop()

        try:
            js = await ipfsop.getJson(path)
            assert js is not None
        except Exception:
            return {}
        else:
            return js

    @opSlot(str, QJsonValue)
    async def pin(self, path: str, options):
        ipfsop = self.app.ipfsOperatorForLoop()

        opts = self._dict(options)
        timeout = opts.get('timeout', 60 * 10)

        try:
            success = False
            async for status in ipfsop.pin2(path, timeout=timeout):
                if status[1] == 1:
                    success = True
                    break
        except Exception:
            traceback.print_exc()

        return success

    @opSlot(str, str)
    async def gpin(self, path: str, qname: str):
        """
        Queue for pinning via ipfsop.ctx
        """
        ipfsop = self.app.ipfsOperatorForLoop()

        try:
            await ipfsop.ctx.pin(path, qname=qname)
        except Exception:
            traceback.print_exc()
            return False

        return True

    @opSlot(str, QJsonValue)
    async def unpin(self, path: str, options):
        ipfsop = self.app.ipfsOperatorForLoop()

        opts = self._dict(options)
        recursive = opts.get('recursive', True)

        try:
            result = await ipfsop.unpin(path, recursive=recursive)
            assert 'Pins' in result
        except Exception:
            return False
        else:
            return True

    @opSlot(str, QJsonValue)
    async def unpackToIpfs(self, path: str, options):
        """
        Extract a zip (or other archive in the future) to an IPFS
        UnixFS directory and return its CID.

        The path argument can be a filepath or an IPFS unixfs path
        """

        opts = self._dict(options)
        timeout = opts.get('timeout', None)
        mime = opts.get('mimeType', 'application/x-zip')
        sourceUrl = opts.get('sourceUrl')

        try:
            ipfsop = self.app.ipfsOperatorForLoop()
            dstdir = tempfile.mkdtemp(prefix='ipfsunzip')
            fp = Path(path)
            ipfsPath = IPFSPath(path)

            if fp.is_file():
                with zipfile.ZipFile(str(fp), 'r') as zip:
                    zip.extractall(dstdir)

            elif ipfsPath.valid:
                data = await ipfsop.catObject(
                    path,
                    timeout=timeout
                )
                assert data is not None

                with zipfile.ZipFile(io.BytesIO(data), 'r') as zip:
                    zip.extractall(dstdir)
            else:
                raise ValueError(f'Cannot handle: {path}')

            entry = await ipfsop.addPath(dstdir, recursive=True)
            assert entry

            shutil.rmtree(dstdir)

            return {
                'cid': entry['Hash'],
                'mimeType': mime,
                'sourceUrl': sourceUrl
            }
        except Exception:
            traceback.print_exc()
            return QVariant(None)

    @opSlot(str, QJsonValue)
    async def list(self, path: str, options):
        try:
            return [obj async for obj in
                    self.app.ipfsOperatorForLoop().list(path)]
        except Exception:
            return []

    @opSlot(str, int)
    async def stat(self, path: str, timeout: int):
        return await (self.app.ipfsOperatorForLoop()).objStat(
            path, timeout=timeout)

    @opSlot(str, str, QJsonValue)
    async def pinRemoteAdd(self, serviceName, path, options):
        ipfsop = self.app.ipfsOperatorForLoop()

        opts = self._dict(options)
        background = opts.get('background', True)
        name = opts.get('name', None)

        try:
            return await ipfsop.pinRemoteAdd(
                serviceName,
                path,
                background=background,
                name=name
            )
        except Exception:
            traceback.print_exc()
            return False
        else:
            return True

    @opSlot(str, QJsonValue)
    async def pinRemoteList(self, serviceName, options):
        ipfsop = self.app.ipfsOperatorForLoop()

        opts = self._dict(options)
        name = opts.get('name', None)
        status = opts.get('status', ['pinned'])

        try:
            return await ipfsop.pinRemoteList(
                serviceName,
                name=name,
                status=status
            )
        except Exception:
            traceback.print_exc()
            return []

    @opSlot(str, QJsonValue)
    async def pinRemoteRemove(self, serviceName, options):
        ipfsop = self.app.ipfsOperatorForLoop()

        opts = self._dict(options)
        name = opts.get('name', None)
        cid = opts.get('cid', None)
        status = opts.get('status', ['pinned'])
        force = opts.get('force', False)

        try:
            return await ipfsop.pinRemoteRemove(
                serviceName,
                name=name,
                cid=cid,
                status=status,
                force=force
            )
        except Exception:
            traceback.print_exc()
            return []

    @tcSlot(str, str)
    async def isPinnedSync(self, path: str, pinType: str):
        return await (self.app.ipfsOperatorForLoop()).isPinned(
            path, pinType=pinType)

    @opSlot(str, str)
    async def isPinned(self, path: str, pinType: str):
        return await (self.app.ipfsOperatorForLoop()).isPinned(
            path, pinType=pinType)

    @opSlot(str, QJsonValue)
    async def resolve(self, path: str, options):
        return await (self.app.ipfsOperatorForLoop()).resolve(path)

    @opSlot(str, QJsonValue)
    async def detectMimeType(self, path: str, options):
        mType = await detectMimeType(path)
        if mType:
            return str(mType)

        return 'application/unknown'

    @tcSlot()
    async def pinRemoteServiceListSync(self):
        ipfsop = self.app.ipfsOperatorForLoop()
        try:
            services = await ipfsop.pinRemoteServiceList()
            assert isinstance(services, list)
        except Exception:
            return []
        else:
            return services

    @pyqtSlot(str, QJsonValue, result=bool)
    def psJsonSend(self, topic, message):
        ensure(self.a_psJsonSend(
            self.app, self.app.loop, topic, self._dict(message)))
        return True

    @pyqtSlot(str, result=bool)
    def psJsonChannelDestroy(self, topic):
        app = runningApp()

        async def stopService(srv):
            app.ipfsCtx.pubsub.unreg(srv)
            await srv.stopListening()

        service = app.ipfsCtx.pubsub.byTopic(topic)
        if service:
            ensureSafe(stopService(service))
            return True

        return False

    @opSlot(str, QJsonValue)
    async def psJsonChannelCreate(self, topic, options):
        service = self.app.ipfsCtx.pubsub.byTopic(topic)
        if service:
            return False

        try:
            opts = self._dict(options)
            lifetime = int(opts.get('lifetime', 0))
            filterSelf = bool(opts.get('filterSelf', True))
            encryption = opts.get('encryption', None)
        except Exception:
            lifetime = 0

        if encryption == 'curve25519':
            service = Curve25519JSONPubsubService(
                self.app.ipfsCtx,
                topic,
                None,
                scheduler=self.app.scheduler,
                metrics=False,
                serveLifetime=lifetime,
                filterSelfMessages=filterSelf
            )
        else:
            service = JSONPubsubService(
                self.app.ipfsCtx, topic=topic,
                scheduler=self.app.scheduler,
                metrics=False,
                serveLifetime=lifetime,
                filterSelfMessages=filterSelf
            )

        self.app.ipfsCtx.pubsub.reg(service)

        await service.startListening()

        return True

    @pyqtSlot(str, str, str, QJsonValue, result=QVariant)
    def p2pHttpJsonGet(self, peerId, protocol, path, body):
        return self.tc(
            self.a_streamRequest,
            peerId,
            protocol,
            path,
            self._dict(body)
        )


class IpfsObjectInterface(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._ipfsPath = IPFSPath(None)

    def _getAddress(self):
        return str(self._ipfsPath)

    def _setAddress(self, addr: str):
        self._ipfsPath = IPFSPath(addr, autoCidConv=True)

    @pyqtSlot(result=str)
    def objPath(self):
        if self._ipfsPath.valid:
            return self._ipfsPath.objPath

        return ''

    @pyqtSlot(result=str)
    def fragment(self):
        if self._ipfsPath.valid:
            return self._ipfsPath.fragment

        return ''

    @pyqtSlot(result=str)
    def basename(self):
        if self._ipfsPath.valid and self._ipfsPath.basename:
            return self._ipfsPath.basename

        return ''

    @pyqtSlot(result=str)
    def dirname(self):
        if self._ipfsPath.valid and self._ipfsPath.dirname:
            return self._ipfsPath.dirname

        return ''

    @pyqtSlot(result=str)
    def ipnsId(self):
        if self._ipfsPath.valid and self._ipfsPath.ipnsId:
            return self._ipfsPath.ipnsId

        return ''

    @pyqtSlot(result=str)
    def ipfsUrl(self):
        if self._ipfsPath.valid:
            return self._ipfsPath.ipfsUrl

        return ''

    @pyqtSlot(result=str)
    def dwebUrl(self):
        if self._ipfsPath.valid:
            return self._ipfsPath.dwebUrl

        return ''

    @pyqtSlot(result=str)
    def ipfsUrlEncoded(self):
        if self._ipfsPath.valid:
            return self._ipfsPath.ipfsUrlEncoded

        return ''

    @pyqtSlot(result=bool)
    def valid(self):
        return self._ipfsPath.valid

    @pyqtSlot(result=bool)
    def isIpfs(self):
        return self._ipfsPath.isIpfs

    @pyqtSlot(result=bool)
    def isIpns(self):
        return self._ipfsPath.isIpns

    @pyqtSlot(result=str)
    def rootCid(self):
        if self._ipfsPath.valid:
            return self._ipfsPath.rootCid

        return ''

    @pyqtSlot(str, result=str)
    def child(self, subpath: str):
        if not self._ipfsPath.valid:
            return ''

        ch = self._ipfsPath.child(subpath)
        if ch and ch.valid:
            return str(ch)

        return ''

    @pyqtSlot(result=str)
    def parent(self):
        pa = self._ipfsPath.parent()
        if pa and pa.valid:
            return str(pa)

        return ''

    @pyqtSlot(result=str)
    def root(self):
        r = self._ipfsPath.root()
        if r and r.valid:
            return str(r)

        return ''

    @pyqtSlot(result=str)
    def publicGwUrl(self):
        if self._ipfsPath.valid:
            return self._ipfsPath.publicGwUrl

        return ''

    address = pyqtProperty(
        'QString', _getAddress, _setAddress)
