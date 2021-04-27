
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import QVariant

from galacteek import services
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.core import uid4

from . import AsyncChanObject


class LDInterface(object):
    @property
    def rdfService(self):
        return services.getByDotName('ld.rdf.stores')

    async def ipfsToRdf(self, app, loop, ipfsPath):
        ipfsop = app.ipfsOperatorForLoop(loop)

        try:
            return await self.rdfService.storeDag(
                ipfsop, str(ipfsPath))
        except Exception:
            import traceback
            traceback.print_exc()
            return False

        return True

    async def a_iObjectCreate(self, app, loop, oid, obj):
        ipfsop = app.ipfsOperatorForLoop(loop)
        uid = uid4()

        # ldType = obj.get('@type')
        uri = f'i:/{uid}'

        dag = {
            "@context": {
                "@vocab": "ips://galacteek.ld/",
                "@base": "ips://galacteek.ld/"
            }
        }
        dag.update(dict(obj))
        cid = await ipfsop.dagPut(dag)

        if 0:
            cid = await ipfsop.dagPut({
                "@context": {
                    "@vocab": "ips://galacteek.ld/",
                    "@base": "ips://galacteek.ld/"
                },

                "@id": uri,
                "@graph": [obj]
            })

        try:
            return await self.rdfService.storeDag(ipfsop, IPFSPath(cid))
        except Exception:
            return False


class LDHandler(AsyncChanObject, LDInterface):
    """
    Linked Data channel interface
    """

    @pyqtSlot(str, result=bool)
    def rdfMe(self, ipfsObjPath: str):
        return self.tc(self.ipfsToRdf, IPFSPath(ipfsObjPath))

    @pyqtSlot(str, QVariant, result=bool)
    def iObjectCreate(self, oid, obj):
        return self.tc(self.a_iObjectCreate, oid, obj.toVariant())
