
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import QVariant

from . import AsyncChanObject


class IPIDInterface(object):
    async def _ipid(self, ipfsCtx):
        curProfile = ipfsCtx.currentProfile
        return await curProfile.userInfo.ipIdentifier()

    async def a_didGet(self, app, loop):
        ipfsop = app.ipfsOperatorForLoop(loop)
        ipid = await self._ipid(ipfsop.ctx)

        if ipid:
            return ipid.did

        return ''

    async def a_serviceEndpointCompact(self, app, loop, path):
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
        service = await ipid.searchServiceById(
            ipid.didUrl(path=path)
        )
        if service:
            async with ipid.editService(ipid.didUrl(path=path)) as editor:
                editor.service['serviceEndpoint'].update(obj)

                return True

            print(service._srv)
        return False

    async def a_ipidCompact(self, app, loop):
        ipfsop = app.ipfsOperatorForLoop(loop)
        ipid = await self._ipid(ipfsop.ctx)

        compact = await ipid.compact()

        return QVariant(compact)


class IPIDHandler(AsyncChanObject, IPIDInterface):
    """
    IPID channel interface
    """

    @pyqtSlot(result=str)
    def did(self):
        return self.tc(self.a_didGet)

    @pyqtSlot(str, result=QVariant)
    def serviceEndpointCompact(self, path):
        return self.tc(self.a_serviceEndpointCompact, path)

    @pyqtSlot(str, QVariant, result=bool)
    def serviceEndpointPatch(self, path, obj):
        return self.tc(
            self.a_serviceEndpointPatch,
            path, obj.toVariant()
        )

    @pyqtSlot(result=QVariant)
    def passportGet(self):
        return self.tc(self.a_dwebPassportGetRaw)

    @pyqtSlot(result=QVariant)
    def compacted(self):
        return self.tc(self.a_ipidCompact)
