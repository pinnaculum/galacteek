import os
import os.path
import asyncio
import aioipfs
import aiofiles

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
from galacteek.ipfs import StatInfo
from galacteek.ipfs.mimetype import MIMEType
from galacteek.ipfs.mimetype import detectMimeType
from galacteek.ipfs.mimetype import detectMimeTypeFromBuffer

from galacteek.ipfs.cidhelpers import IPFSPath
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
    objectOpened = pyqtSignal(IPFSPath)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.app = QApplication.instance()
        self.setObjectName('resourceOpener')

    @ipfsOp
    async def open(self, ipfsop, pathRef, mimeType=None):
        """
        Open the resource referenced by rscPath according
        to its MIME type

        :param pathRef: IPFS path (can be str or IPFSPath)
        :param MIMEType mimeType: MIME type
        """

        ipfsPath = None
        statInfo = None

        if isinstance(pathRef, IPFSPath):
            ipfsPath = pathRef
        elif isinstance(pathRef, str):
            ipfsPath = IPFSPath(pathRef)
        else:
            raise ValueError('Invalid input value')

        if not ipfsPath.valid:
            return False

        rscPath = ipfsPath.objPath

        if self.app.mainWindow.pinAllGlobalChecked and not ipfsPath.isIpns:
            ensure(ipfsop.ctx.pinner.queue(rscPath, False,
                                           None,
                                           qname='default'))

        rscShortName = shortPathRepr(rscPath)

        if ipfsPath.isIpfs:
            # Try to reuse metadata from the multihash store
            rscMeta = await self.app.multihashDb.get(rscPath)
            if rscMeta:
                cachedMime = rscMeta.get('mimetype')
                cachedStat = rscMeta.get('stat')
                if cachedMime:
                    mimeType = MIMEType(cachedMime)
                if cachedStat:
                    statInfo = StatInfo(cachedStat)

        if mimeType is None:
            mimeType = await detectMimeType(rscPath)

        if mimeType and mimeType.valid:
            logUser.info('{path} ({type}): opening'.format(
                path=rscPath, type=str(mimeType)))
        else:
            return messageBox(iResourceCannotOpen(rscPath))

        if mimeType.type == 'application/octet-stream':
            # Try to decode the
            logUser.info('{path} ({type}): RSA-encoded data! Trying ..'.format(
                path=rscPath, type=str(mimeType)))

            if statInfo is None:
                statInfo = StatInfo(await ipfsop.objStat(rscPath, timeout=5))

            profile = ipfsop.ctx.currentProfile
            if profile and statInfo and statInfo.dataSmallerThan(1000000):
                logUser.info('{path}: RSA on the way ..')

                data = await ipfsop.catObject(ipfsPath.objPath, timeout=5)
                if not data:
                    # XXX
                    return

                decrypted = await profile.rsaAgent.decrypt(data)

                if decrypted:
                    # "Good evening, 007"
                    #
                    # Create a short-lived IPFS block that will be burned
                    # by the resource opener after opening
                    # 
                    # We know it's wrong
                    #

                    # Write the deciphered data to a temp file
                    encFpath = self.app.tempDir.filePath('onetoomany.enc')
                    async with aiofiles.open(encFpath, 'w+b') as fd:
                        await ipfsop.sleep()
                        await fd.write(decrypted)

                    # Burn it in a block
                    entry = await ipfsop.client.block.put(encFpath)
                    #entry = await ipfsop.client.add_bytes(decrypted)
                    if not entry:
                        # XXX
                        return

                    if 0:
                        logUser.info(
                            '{path}: RSA OK! spawning child: {child}'.format(
                                child=entry['Hash']))

                    # Open the data from the block!
                    ensure(self.openBlock(entry['Key']))

        elif mimeType.isText:
            tab = ipfsview.TextViewerTab()
            tab.show(rscPath)
            self.objectOpened.emit(ipfsPath)
            return self.app.mainWindow.registerTab(
                tab,
                rscShortName,
                icon=getMimeIcon('text/x-generic'),
                tooltip=rscPath,
                current=True
            )

        if mimeType.isImage:
            tab = ImageViewerTab(self.app.mainWindow)
            ensure(tab.view.showImage(rscPath))
            self.objectOpened.emit(ipfsPath)
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
            self.objectOpened.emit(ipfsPath)
            return self.app.mainWindow.registerTab(
                tab,
                rscShortName,
                icon=getMimeIcon('application/pdf'),
                tooltip=rscPath,
                current=True
            )

        if mimeType.isDir or ipfsPath.isIpns or mimeType.isHtml:
            self.objectOpened.emit(ipfsPath)
            return self.app.mainWindow.addBrowserTab().browseFsPath(ipfsPath)

        logUser.info('{path} ({type}): unhandled resource type'.format(
            path=rscPath, type=str(mimeType)))

    @ipfsOp
    async def openBlock(self, ipfsop, pathRef, mimeType=None):
        ipfsPath = None
        statInfo = None

        if isinstance(pathRef, IPFSPath):
            ipfsPath = pathRef
        elif isinstance(pathRef, str):
            ipfsPath = IPFSPath(pathRef)
        else:
            raise ValueError('Invalid input value')

        if not ipfsPath.valid:
            return False

        blockStat = await ipfsop.waitFor(
            ipfsop.client.block.stat(pathRef), 5
        )

        if not blockStat or not isinstance(blockStat, dict):
            messageBox('Block is bad')

        blockSize = blockStat.get('Size')

        if blockSize > (1024 * 1024 * 16):
            # XXX
            return

        logUser.info('Block {path}: Opening'.format(path=pathRef))

        blockData = await ipfsop.client.block.get(pathRef)

        rscPath = ipfsPath.objPath
        rscShortName = rscPath
        mimeType = await detectMimeTypeFromBuffer(blockData[:1024])

        if mimeType and mimeType.valid:
            logUser.info('Block: {path} ({type}): opening'.format(
                path=rscPath, type=str(mimeType)))
        else:
            return messageBox(iResourceCannotOpen(rscPath))

        if mimeType.isImage:
            tab = ImageViewerTab(self.app.mainWindow)
            ensure(tab.view.showImage(rscPath, fromBlock=True))
            self.objectOpened.emit(ipfsPath)
            return self.app.mainWindow.registerTab(
                tab,
                rscShortName,
                icon=getMimeIcon('image/x-generic'),
                tooltip=rscPath,
                current=True
            )


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

        args = progArgs.replace('%f', filePath)
        log.debug('Executing: {}'.format(args))

        try:
            proc = await asyncio.create_subprocess_shell(
                args,
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
            await self.openWithExternal(rscPath, "xdg-open '%f'")
        elif self.app.system == 'Darwin':
            await self.openWithExternal(rscPath, "open '%f'")


class ResourceAnalyzer(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.app = QApplication.instance()

    @ipfsOp
    async def __call__(self, ipfsop, ipfsPath):
        """
        :param IPFSPath ipfsPath
        """

        path = ipfsPath.objPath
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
