from pathlib import Path
import traceback

from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QVariant
from PyQt5.QtCore import QByteArray
from PyQt5.QtCore import QJsonValue
from PyQt5.QtCore import QUrl

from galacteek import log
from galacteek.core import runningApp
from galacteek.core.ps import KeyListener

from galacteek.ipfs.pubsub.messages import PubsubMessage
from galacteek.ipfs.pubsub.service import JSONPubsubService
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

    async def a_psJsonSend(self, app, loop, topic, msg):
        ipfsop = app.ipfsOperatorForLoop(loop)

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

    @opSlot(str)
    async def addStr(self, data):
        ipfsop = self.app.ipfsOperatorForLoop()

        try:
            entry = await ipfsop.addString(data)
            assert entry is not None
        except Exception:
            return {}
        else:
            return entry

    @opSlot(QByteArray)
    async def addBytes(self, data):
        ipfsop = self.app.ipfsOperatorForLoop()

        try:
            entry = await ipfsop.addBytes(bytes(data))
            assert entry is not None
        except Exception:
            return {}
        else:
            return entry

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
    async def pin(self, path, options):
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
        else:
            return success

    @pyqtSlot(str, QJsonValue, result=bool)
    def psJsonSend(self, topic, message):
        return self.tc(self.a_psJsonSend, topic, self._dict(message))

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

    # @pyqtSlot(str, QJsonValue, result=bool)
    @opSlot(str, QJsonValue)
    async def psJsonChannelCreate(self, topic, options):
        # ipfsop = self.app.ipfsOperatorForLoop()
        service = self.app.ipfsCtx.pubsub.byTopic(topic)
        if service:
            return False

        try:
            opts = self._dict(options)
            lifetime = int(opts.get('lifetime', 0))
            filterSelf = bool(opts.get('filterSelf', True))
        except Exception:
            lifetime = 0

        service = JSONPubsubService(
            self.app.ipfsCtx, topic=topic,
            scheduler=self.app.scheduler,
            metrics=False,
            serveLifetime=lifetime,
            filterSelfMessages=filterSelf
        )
        self.app.ipfsCtx.pubsub.reg(service)

        async def startService(srv):
            await srv.startListening()

        await startService(service)

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
