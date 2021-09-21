from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import QJsonValue

from galacteek import services
from galacteek.ipfs.cidhelpers import IPFSPath

from galacteek.core import runningApp
from galacteek.core import utcDatetimeIso

from galacteek.ld import gLdBaseUri
from galacteek.ld.signatures import jsonldsig
from galacteek.ld.iri import *

from . import AsyncChanObject


class LDInterface(object):
    @property
    def rdfService(self):
        return services.getByDotName('ld.pronto.graphs')

    @property
    def iService(self):
        return services.getByDotName('dweb.schemes.i')

    async def ipfsToRdf(self, app, loop, ipfsPath):
        ipfsop = app.ipfsOperatorForLoop(loop)

        try:
            return await self.rdfService.storeObject(
                ipfsop, str(ipfsPath))
        except Exception:
            return False

        return True

    async def a_iObjectCreate(self, app, loop, oid, obj):
        ipfsop = app.ipfsOperatorForLoop(loop)
        curProfile = ipfsop.ctx.currentProfile

        try:
            # Get the IPID and private key
            ipid = await curProfile.userInfo.ipIdentifier()
            assert ipid is not None

            passport = await ipid.searchServiceById(
                ipid.didUrl(path='/passport')
            )

            rsaAgent = await ipid.rsaAgentGet(ipfsop)
            privKey = await rsaAgent._privateKey()

            assert privKey is not None

            # Initial DAG structure
            dag = {
                "@context": {
                    "@vocab": gLdBaseUri,
                    "@base": gLdBaseUri
                }
            }

            dag.update(dict(obj))

            if passport:
                # Author
                dag['author'] = {
                    '@type': 'Person',
                    '@id': passport.endpoint['me'].get('@id')
                }

            # Dates
            if 'dateCreated' not in dag:
                dag['dateCreated'] = utcDatetimeIso()
            if 'dateModified' not in dag:
                dag['dateModified'] = utcDatetimeIso()

            # JSON-LD signature
            signed = jsonldsig.sign(dag, privKey.exportKey())

            # Store in IPFS
            cid = await ipfsop.dagPut(signed)

            # Notify the RDF service
            await runningApp().s.rdfStore(IPFSPath(cid))

            # Return the CID of the object
            return cid
        except Exception as err:
            log.debug(f'Error creating object: {err}')
            return ''


class LDHandler(AsyncChanObject, LDInterface):
    """
    Linked Data channel interface
    """

    @property
    def iService(self):
        return services.getByDotName('dweb.schemes.i')

    @pyqtSlot(str, result=bool)
    def rdfMe(self, ipfsObjPath: str):
        return self.tc(self.ipfsToRdf, IPFSPath(ipfsObjPath))

    @pyqtSlot(str, result=str)
    def iObjectUriGen(self, oclass):
        return self.iService.iriGenObject(oclass)

    @pyqtSlot(str, QJsonValue, result=str)
    def iObjectCreate(self, oid, obj):
        return self.tc(self.a_iObjectCreate, oid, self._dict(obj))

    @pyqtSlot(QJsonValue, result=str)
    def iObjectCreateAuto(self, data):
        obj = self._dict(data)
        if obj:
            _type = obj.get('@type')
            if not _type:
                return

            oid = self.iService.iriGenObject(_type)
            obj['@id'] = oid

            return self.tc(self.a_iObjectCreate, oid, obj)
