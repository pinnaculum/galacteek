from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import QVariant
from PyQt5.QtCore import QJsonValue

from . import GAsyncObject


class IPIDInterface(object):
    async def _ipid(self, ipfsCtx):
        curProfile = ipfsCtx.currentProfile
        return await curProfile.userInfo.ipIdentifier()

    async def a_didGet(self, app, loop):
        ipfsop = app.ipfsOperatorForLoop(loop)
        ipid = await self._ipid(ipfsop.ctx)

        if ipid:
            return ipid.did
        else:
            return ''

    async def a_serviceEndpointCompact(self, app, loop, did, path):
        ipfsop = app.ipfsOperatorForLoop(loop)

        ipid = await self._ipid(ipfsop.ctx)
        service = await ipid.searchServiceById(
            ipid.didUrl(path=path)
        )

        if service:
            comp = await service.compact()
            return QVariant(comp['serviceEndpoint'])

        return QVariant({})

    async def a_serviceEndpointPatch(self, app, loop, path, obj):
        ipfsop = app.ipfsOperatorForLoop(loop)

        ipid = await self._ipid(ipfsop.ctx)
        if not ipid:
            return False

        service = await ipid.searchServiceById(
            ipid.didUrl(path=path)
        )

        if service and isinstance(obj, dict):
            # Patch

            await service.request(command='MERGE', body=obj)
            return True

        return False

    async def a_passportVcAdd(self, app, loop, vc):
        ipfsop = app.ipfsOperatorForLoop(loop)

        ipid = await self._ipid(ipfsop.ctx)
        if not ipid:
            return False

        service = await ipid.searchServiceById(
            ipid.didUrl(path='/passport')
        )

        if service and isinstance(vc, dict):
            vcid = vc.get('@id')
            await service.request(command='VCADD', vcid=vcid)

            return True

        return False

    async def a_passportVcSetMain(self, app, loop, vc):
        ipfsop = app.ipfsOperatorForLoop(loop)

        ipid = await self._ipid(ipfsop.ctx)
        if not ipid:
            return False

        service = await ipid.searchServiceById(
            ipid.didUrl(path='/passport')
        )

        if service and isinstance(vc, dict):
            await service.request(command='VCSETMAIN', body=vc)

            return True

        return False

    async def a_ipidCompact(self, app, loop):
        ipfsop = app.ipfsOperatorForLoop(loop)
        ipid = await self._ipid(ipfsop.ctx)

        compact = await ipid.compact()
        return QVariant(compact)


class IPIDHandler(GAsyncObject, IPIDInterface):
    """
    IPID channel interface
    """

    @pyqtSlot(result=str)
    def did(self):
        return self.tc(self.a_didGet)

    @pyqtSlot(str, str, result=QVariant)
    def serviceEndpointCompact(self, did, path):
        return self.tc(self.a_serviceEndpointCompact, did, path)

    @pyqtSlot(str, QVariant, result=bool)
    def serviceEndpointPatch(self, path, value):
        """
        Patch a DID service endpoint with an object (dictionary)
        """

        try:
            obj = dict(value.toVariant())
        except Exception:
            return False

        return self.tc(
            self.a_serviceEndpointPatch,
            path, obj
        )

    @pyqtSlot(result=QVariant)
    def passportGet(self):
        return self.tc(self.a_dwebPassportGetRaw)

    @pyqtSlot(QJsonValue, result=QVariant)
    def passportVcAdd(self, vc):
        return self.tc(self.a_passportVcAdd, self._dict(vc))

    @pyqtSlot(QJsonValue, result=QVariant)
    def passportVcSetMain(self, vc):
        return self.tc(self.a_passportVcSetMain, self._dict(vc))

    @pyqtSlot(result=QVariant)
    def compacted(self):
        return self.tc(self.a_ipidCompact)
