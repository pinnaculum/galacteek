from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import QVariant
from PyQt5.QtCore import QJsonValue

from galacteek import log
from galacteek import ensure
from galacteek import cached_property

from galacteek.core.models.unixfs import UnixFSDirectoryModel
from galacteek.core.models.unixfs import UnixFSModelAgent
from galacteek.core.models.unixfs import UnixFsRoles
from galacteek.core.models.unixfs import UnixFsNameRole
from galacteek.core.models.unixfs import UnixFsSizeRole
from galacteek.core.models.unixfs import UnixFsHashRole
from galacteek.core.models.unixfs import UnixFsTypeRole
from galacteek.core.models.unixfs import UnixFsMimeRole
from galacteek.core.models.unixfs import UnixFsIpfsPathRole
from galacteek.core.models.unixfs import UnixFsIpfsUrlRole

from galacteek.ipfs.cidhelpers import IPFSPath

from . import GAsyncObject
import qasync


class UnixFsDirModel(UnixFSDirectoryModel, GAsyncObject):
    @cached_property
    def agent(self):
        return UnixFSModelAgent(self)

    @qasync.asyncSlot(str, QJsonValue)
    async def ls(self, dirPath: str, options):
        ipfsop = self.app.ipfsOperatorForLoop()
        path = IPFSPath(dirPath, autoCidConv=True)

        if path.valid:
            ensure(self.agent.listDirectory(
                ipfsop, str(path)))

    @pyqtSlot()
    def clear(self):
        self.clearModel()

    def roleNames(self):
        return UnixFsRoles

    def data(self, index, role):
        if not index.isValid():
            return QVariant(None)

        try:
            item = self.entries[index.row()]

            ipfsPath = IPFSPath(
                item['Hash'], autoCidConv=True)
            assert ipfsPath.valid

            if role == UnixFsNameRole:
                return item['Name']
            elif role == UnixFsHashRole:
                return item['Hash']
            elif role == UnixFsTypeRole:
                return item['Type']
            elif role == UnixFsSizeRole:
                return item['Size']
            elif role == UnixFsMimeRole:
                if item['Type'] == 1:
                    return 'application/x-directory'

                mType = self.app.mimeDb.mimeTypeForFile(
                    item['Name'])

                if mType:
                    return mType.name()

                return 'application/unknown'
            elif role == UnixFsIpfsPathRole:
                return str(ipfsPath.objPath)
            elif role == UnixFsIpfsUrlRole:
                return str(ipfsPath.ipfsUrl)
        except Exception as err:
            log.debug(f'data() error: {err}')

        return None
