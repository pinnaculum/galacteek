import traceback
from rdflib import URIRef

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QJsonValue

from galacteek import log
from galacteek import services
from galacteek.ipfs.cidhelpers import IPFSPath

from galacteek.core import uid4
from galacteek.core import runningApp
from galacteek.core import utcDatetimeIso

from galacteek.ld import gLdBaseUri
from galacteek.ld import ontolochain

from . import GOntoloObject
from . import tcSlot
from . import opSlot


class OntoloChainInterface(object):
    async def a_ontoloCreateObject(self, ipfsop,
                                   recType, obj, opts):
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

            dag = {}

            if '@context' not in obj:
                dag.update({
                    "@context": {
                        "@vocab": gLdBaseUri,
                        "@base": gLdBaseUri
                    }
                })

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

            dag['verificationMethod'] = f'{ipid.did}#keys-1'

            # Store in IPFS
            cid = await ipfsop.dagPut(dag)

            # Notify the RDF service
            await runningApp().s.rdfStore(
                IPFSPath(cid),
                recordType=recType,
                chainUri=URIRef(self.chainUri),
                outputGraph=self.graphUri
            )

            # Return the CID of the object
            return cid
        except Exception as err:
            log.debug(f'Error creating object: {err}')
            return ''


class OntoloChainHandler(GOntoloObject, OntoloChainInterface):
    rdfMergeResult = pyqtSignal(str, bool)

    @property
    def pronto(self):
        return services.getByDotName('ld.pronto')

    @property
    def rsc(self):
        return ontolochain.OntoloChain(
            self.pronto.historyService,
            URIRef(self.chainUri)
        )

    @tcSlot(result=str)
    async def didMainChainUri(self):
        ipfsop = self.app.ipfsOperatorForLoop()
        ipid = await ipfsop.ipid()

        if ipid:
            return str(ontolochain.didMainChainUri(ipid))

    @tcSlot(str, result=str)
    async def subDidChainUri(self, name: str):
        ipfsop = self.app.ipfsOperatorForLoop()
        ipid = await ipfsop.ipid()

        if ipid:
            return str(ontolochain.subDidChainUri(ipid, name))

    @tcSlot(result=str)
    async def subDidChainUuidUri(self):
        ipfsop = self.app.ipfsOperatorForLoop()
        ipid = await ipfsop.ipid()

        if ipid:
            return str(ontolochain.subDidChainUri(ipid, uid4()))

    @opSlot()
    async def create(self):
        ipfsop = self.app.ipfsOperatorForLoop()

        try:
            ipid = await ipfsop.ipid()

            await ontolochain.create(self.pronto.graphHistory,
                                     ipid,
                                     URIRef(self.chainUri),
                                     ipfsop.ctx.node.id)
            return True
        except Exception:
            traceback.print_exc()
            return False

    @opSlot(QJsonValue, QJsonValue)
    async def objectAppend(self, jsObj, jsOpts):
        return await self.a_ontoloCreateObject(
            self.app.ipfsOperatorForLoop(),
            'OntoloChainRecord',
            self._dict(jsObj),
            self._dict(jsOpts)
        )

    @opSlot(QJsonValue, QJsonValue)
    async def ontoloVcStore(self, jsVc, jsOpts):
        return await self.a_ontoloCreateObject(
            self.app.ipfsOperatorForLoop(),
            'OntoloChainVCRecord',
            self._dict(jsVc),
            self._dict(jsOpts)
        )

    @opSlot(QJsonValue, QJsonValue)
    async def geoEmitterAttach(self, jsObj, jsOpts):
        try:
            obj = self._dict(jsObj)
            obj['dateCreated'] = utcDatetimeIso()

            await self.pronto.graphHistory.pullObject(obj)
        except Exception:
            traceback.print_exc()

    @opSlot(QJsonValue, QJsonValue)
    async def geoTransponderAttach(self, jsObj, jsOpts):
        try:
            obj = self._dict(jsObj)
            obj['dateCreated'] = utcDatetimeIso()

            await self.pronto.graphHistory.pullObject(obj)
        except Exception:
            traceback.print_exc()
