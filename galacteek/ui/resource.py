import os
import os.path
import asyncio
import aioipfs

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import QObject
from PyQt5.QtCore import pyqtSignal

from galacteek import log
from galacteek import logUser
from galacteek import ensure

from galacteek.dweb.page import PDFViewerPage
from galacteek.dweb.page import WebTab
from galacteek.dweb.page import DWebView

from galacteek.ipfs import ipfsOp
from galacteek.ipfs.mimetype import MIMEType
from galacteek.ipfs.mimetype import detectMimeType

from galacteek.ipfs.cidhelpers import isIpfsPath
from galacteek.ipfs.cidhelpers import isIpnsPath
from galacteek.ipfs.cidhelpers import shortPathRepr

from galacteek.crypto.qrcode import IPFSQrDecoder

from . import ipfsview
from .helpers import getMimeIcon
from .helpers import messageBox
from .imgview import ImageViewerTab


def iResourceCannotOpen(path):
    return QCoreApplication.translate(
        'resourceOpener',
        '{}: cannot determine resource type or timeout occured '
        '(check connectivity)').format(
            path)


class IPFSResourceOpener(QObject):
    objectOpened = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.app = QApplication.instance()
        self.setObjectName('resourceOpener')

    @ipfsOp
    async def open(self, ipfsop, rscPath, mimeType=None):
        """
        Open the resource referenced by rscPath according
        to its MIME type

        :param str rscPath: IPFS CID/path
        :param MIMEType mimeType: MIME type
        """

        if self.app.mainWindow.pinAllGlobalChecked and not isIpnsPath(rscPath):
            ensure(ipfsop.ctx.pinner.queue(rscPath, False,
                                           None,
                                           qname='default'))

        rscShortName = shortPathRepr(rscPath)

        if isIpfsPath(rscPath):
            # Try to reuse metadata from the multihash store
            rscMeta = await self.app.multihashDb.get(rscPath)
            if rscMeta:
                value = rscMeta.get('mimetype')
                if value:
                    mimeType = MIMEType(value)

        if mimeType is None:
            mimeType = await detectMimeType(rscPath)

        if mimeType and mimeType.valid:
            logUser.info('{path} ({type}): opening'.format(
                path=rscPath, type=str(mimeType)))
        else:
            return messageBox(iResourceCannotOpen(rscPath))

        if mimeType.isText:
            tab = ipfsview.TextViewerTab()
            tab.show(rscPath)
            self.objectOpened.emit(rscPath)
            return self.app.mainWindow.registerTab(
                tab,
                rscShortName,
                icon=getMimeIcon('text/x-generic'),
                tooltip=rscPath,
                current=True
            )

        if mimeType.isImage:
            tab = ImageViewerTab(rscPath, self.app.mainWindow)
            self.objectOpened.emit(rscPath)
            return self.app.mainWindow.registerTab(
                tab,
                rscShortName,
                icon=getMimeIcon('image/x-generic'),
                tooltip=rscPath,
                current=True
            )

        if mimeType.isVideo or mimeType.isAudio:
            tab = self.app.mainWindow.addMediaPlayerTab()
            if tab:
                tab.playFromPath(rscPath)
            return

        if mimeType == 'application/pdf':
            return await self.openWithSystemDefault(rscPath)

        if mimeType == 'application/pdf' and 0:  # not usable yet
            tab = WebTab(self.app.mainWindow)
            tab.attach(
                DWebView(page=PDFViewerPage(rscPath))
            )
            self.objectOpened.emit(rscPath)
            return self.app.mainWindow.registerTab(
                tab,
                rscShortName,
                icon=getMimeIcon('application/pdf'),
                tooltip=rscPath,
                current=True
            )

        if mimeType.isDir or isIpnsPath(rscPath) or mimeType.isHtml:
            self.objectOpened.emit(rscPath)
            return self.app.mainWindow.addBrowserTab().browseFsPath(rscPath)

        logUser.info('{path} ({type}): unhandled resource type'.format(
            path=rscPath, type=str(mimeType)))

    @ipfsOp
    async def openWithExternal(self, ipfsop, rscPath, progArgs):
        filePath = os.path.join(self.app.tempDir.path(),
                                os.path.basename(rscPath))

        if not os.path.exists(filePath):
            try:
                await ipfsop.client.get(rscPath,
                                        dstdir=self.app.tempDir.path())
            except aioipfs.APIError as err:
                log.debug(err.message)
                return

        if not os.path.isfile(filePath):
            # Bummer
            return

        for idx, value in enumerate(progArgs):
            if value == '%f':
                progArgs[idx] = filePath

        try:
            proc = await asyncio.create_subprocess_exec(
                *progArgs,
                stdout=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
        except BaseException as err:
            os.unlink(filePath)
            log.debug(str(err))
        else:
            os.unlink(filePath)

    @ipfsOp
    async def openWithSystemDefault(self, ipfsop, rscPath):
        # Use xdg-open or open depending on the platform
        if self.app.system == 'Linux':
            await self.openWithExternal(rscPath, ['xdg-open', '%f'])
        elif self.app.system == 'Darwin':
            await self.openWithExternal(rscPath, ['open', '%f'])


class ResourceAnalyzer(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.app = QApplication.instance()

    @ipfsOp
    async def __call__(self, ipfsop, path):
        mHashMeta = await self.app.multihashDb.get(path)

        if mHashMeta:
            # Already have metadata for this object
            mimetype = MIMEType(mHashMeta.get('mimetype'))
            statInfo = mHashMeta.get('stat')
            return mimetype, statInfo
        else:
            mimetype = await detectMimeType(path)

            statInfo = await ipfsop.objStat(path)
            if not statInfo or not isinstance(statInfo, dict):
                log.debug('Stat failed for {path}'.format(
                    path=path))
                return mimetype, None

            await ipfsop.sleep()

            # Store retrieved information in the metadata store
            metaMtype = mimetype.type if mimetype and mimetype.valid else None
            await self.app.multihashDb.store(
                path,
                mimetype=metaMtype,
                stat=statInfo
            )

        if mimetype and mimetype.valid:
            return mimetype, statInfo

    @ipfsOp
    async def decodeQrCodes(self, ipfsop, path):
        try:
            data = await ipfsop.waitFor(
                ipfsop.client.cat(path), 12
            )

            if data is None:
                return

            # Decode the QR codes in the image if there's any
            qrDecoder = IPFSQrDecoder()
            if not qrDecoder:
                return

            return qrDecoder.decode(data)
        except aioipfs.APIError:
            pass
