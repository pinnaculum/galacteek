import traceback

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QJsonValue

from galacteek import log
from galacteek import services
from galacteek.ipfs.cidhelpers import IPFSPath

from galacteek.core import runningApp
from galacteek.core import utcDatetimeIso

from galacteek.ld import gLdBaseUri
from galacteek.ld.signatures import jsonldsig
from galacteek.ld import ontolochain

from . import GOntoloObject
from . import tcSlot
from . import opSlot


class OntoloChainInterface(object):
    async def a_ontoloCreateObject(self, app, loop,
                                   recType, obj, opts):
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

            signed = jsonldsig.sign(dag, privKey.exportKey())

            # Store in IPFS
            cid = await ipfsop.dagPut(signed)

            # Notify the RDF service
            await runningApp().s.rdfStore(
                IPFSPath(cid),
                recordType=recType
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

    @opSlot()
    async def create(self):
        ipfsop = self.app.ipfsOperatorForLoop()

        try:
            ipid = await ipfsop.ipid()

            await ontolochain.create(self.pronto.graphHistory,
                                     ipid,
                                     self.chainUri,
                                     ipfsop.ctx.node.id)
            return True
        except Exception:
            traceback.print_exc()
            return False

    @opSlot(QJsonValue, QJsonValue)
    async def objectAppend(self, jsObj, jsOpts):
        ipfsop = self.app.ipfsOperatorForLoop()
        recType = 'OntoloChainRecord'

        try:
            obj = self._dict(jsObj)

            # Get the IPID and private key
            ipid = await ipfsop.ipid()
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

            # JSON-LD signature
            signed = jsonldsig.sign(dag, privKey.exportKey())

            # Store in IPFS
            cid = await ipfsop.dagPut(signed)

            # Notify the RDF service
            await runningApp().s.rdfStore(
                IPFSPath(cid),
                recordType=recType,
                chainUri=self.chainUri,
                outputGraph=self.graphUri
            )

            # Return the CID of the object
            return cid
        except Exception as err:
            traceback.print_exc()
            log.debug(f'Error creating object: {err}')
            return ''
