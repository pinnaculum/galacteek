from typing import Union
import aioipfs

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QObject

from galacteek import log
from galacteek import ensure

from galacteek.ipfs import ipfsOp

from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ipfs.cidhelpers import getCID
from galacteek.ipfs.cidhelpers import cidDowngrade
from galacteek.ipfs.mimetype import MIMEType
from galacteek.ipfs.mimetype import detectMimeType
from galacteek.ipfs.ipfssearch import objectMetadata

from galacteek.crypto.qrcode import IPFSQrDecoder


class ResourceAnalyzer(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.app = QApplication.instance()
        self.qrDecoder = IPFSQrDecoder()

    @ipfsOp
    async def __call__(self, ipfsop, pathRef: Union[IPFSPath, str],
                       fetchExtraMetadata=False,
                       statType: list = ['object'],
                       mimeTimeout=10):
        """
        :param IPFSPath pathRef: path of the resource to analyze
        :param str statType: list of types of stat calls to perform
            (object or files)
        """

        if isinstance(pathRef, IPFSPath):
            ipfsPath = pathRef
        elif isinstance(pathRef, str):
            ipfsPath = IPFSPath(pathRef, autoCidConv=True)
        else:
            log.debug('Invalid path: {path}'.format(path=pathRef))
            return None, None

        path = ipfsPath.objPath
        mHashMeta = await self.app.multihashDb.get(path)

        if mHashMeta:
            # Already have metadata for this object
            typeStr = mHashMeta.get('mimetype')
            mimetype = MIMEType(typeStr) if typeStr else None
            statInfo = mHashMeta.get('stat')
            return mimetype, statInfo
        else:
            mimetype = await detectMimeType(
                path,
                timeout=mimeTimeout
            )

            if 'object' in statType:
                statInfo = await ipfsop.objStatInfo(path)
                if not statInfo:
                    log.debug('Stat failed for {path}'.format(
                        path=path))
                    return mimetype, None
            elif 'files' in statType:
                statInfo = await ipfsop.filesStatInfo(ipfsPath.objPath)
            else:
                raise ValueError('Invalid stat type')

            await ipfsop.sleep()

            # Store retrieved information in the metadata store
            # TODO: use an RDF graph (ideally with automatic purge system)

            metaMtype = mimetype.type if mimetype and mimetype.valid else None

            if 'object' in statType:
                await self.app.multihashDb.store(
                    path,
                    mimetype=metaMtype,
                    stat=statInfo.stat
                )
            elif 'files' in statType:
                await self.app.multihashDb.store(
                    path,
                    mimetype=metaMtype,
                    filesStat=statInfo.stat
                )

            # Fetch additional metadata in another task

            if fetchExtraMetadata and statInfo is not None:
                ensure(self.fetchMetadata(path, statInfo))

        return mimetype, statInfo

    async def fetchMetadata(self, path, sInfo):
        if sInfo is None:
            return

        cidobj = getCID(sInfo.cid)
        cid = cidDowngrade(cidobj)

        if not cid:
            return

        metadata = await objectMetadata(str(cid))

        if metadata:
            await self.app.multihashDb.store(
                path,
                objmetadata=metadata
            )

    @ipfsOp
    async def decodeQrCodes(self, ipfsop, path):
        try:
            data = await ipfsop.catObject(path)

            if data is None:
                log.debug('decodeQrCodes({path}): could not fetch QR')
                return

            if not self.qrDecoder:
                # No QR decoding support
                log.debug('decodeQrCodes: no QR decoder available')
                return

            # Decode the QR codes in the image if there's any
            return await self.app.loop.run_in_executor(
                self.app.executor, self.qrDecoder.decode, data)
        except aioipfs.APIError as err:
            log.debug(f'decodeQrCodes({path}): IPFS error: {err.message}')
