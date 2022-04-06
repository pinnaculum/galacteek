import secrets
import traceback
import os
from pathlib import Path

from rdflib import URIRef
from rdflib import Literal

from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QJsonValue

from galacteek import log
from galacteek import services
from galacteek.ipfs.cidhelpers import IPFSPath

from galacteek.core.tmpf import TmpDir
from galacteek.core import runningApp
from galacteek.core import utcDatetimeIso

from galacteek.ld import gLdBaseUri
from galacteek.ld.iri import *

from . import GAsyncObject
from . import opSlot


class LDInterface(object):
    async def ipfsToRdf(self, app, loop, ipfsPath):
        ipfsop = app.ipfsOperatorForLoop(loop)

        try:
            return await self.rdfService.storeObject(
                ipfsop, str(ipfsPath))
        except Exception:
            return False

        return True

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

            cid = await ipfsop.dagPut(dag)

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

    async def a_ipgRdfMergeFromIpfs(self,
                                    mergeId, ipfsPath, uri):
        app = self.app
        ipfsop = app.ipfsOperatorForLoop()
        graph = self.rdfService.graphByUri(uri)

        if graph is None:
            return mergeId

        try:
            with TmpDir() as dir:
                await ipfsop.client.core.get(
                    ipfsPath, dstdir=dir)

                for fn in os.listdir(dir):
                    fp = Path(dir).joinpath(fn)
                    await self.app.rexec(graph.parse, str(fp))

            self.rdfMergeResult.emit(mergeId, True)
        except Exception:
            traceback.print_exc()
            self.rdfMergeResult.emit(mergeId, False)
            return False

        # return mergeId
        return True

    async def a_ipgRdfMergeFromFile(self,
                                    mergeId, fp, uri):
        app = runningApp()
        graph = self.rdfService.graphByUri(uri)
        if graph is None:
            return False

        f = Path(fp)

        if not f.is_file():
            self.rdfMergeResult.emit(mergeId, False)
            return False

        try:
            await app.rexec(graph.parse, str(f))
            self.rdfMergeResult.emit(mergeId, True)
        except Exception:
            self.rdfMergeResult.emit(mergeId, False)

    async def a_ipgObjectStore(self, app, loop,
                               uri, obj: dict):
        graph = self.rdfService.graphByUri(uri)

        if graph is None:
            return False

        await graph.pullObject(obj)
        return True

    async def a_ipgTripleAdd(self, app, loop,
                             guri, s, p, o):
        graph = self.rdfService.graphByUri(guri)

        if graph is None:
            return False

        graph.add((URIRef(s), URIRef(p), o))
        return True


class LDHandler(GAsyncObject, LDInterface):
    """
    Linked Data channel interface
    """

    rdfMergeResult = pyqtSignal(str, bool)

    @property
    def rdfService(self):
        return services.getByDotName('ld.pronto')

    @property
    def iService(self):
        return services.getByDotName('dweb.schemes.i')

    @pyqtSlot(str, result=bool)
    def rdfMe(self, ipfsObjPath: str):
        return self.tc(self.ipfsToRdf, IPFSPath(ipfsObjPath))

    @opSlot(str, str)
    async def ipgRdfMergeFromIpfs(self, graphUri: str, ipfsPath: str):
        mid = secrets.token_hex(12)

        return await self.a_ipgRdfMergeFromIpfs(
            mid,
            ipfsPath, graphUri
        )

    @opSlot(str, str, result=str)
    async def ipgRdfMergeFromFile(self, graphUri: str, fp: str):
        return await self.a_ipgRdfMergeFromFile(mid, fp, graphUri)

    @pyqtSlot(str, QJsonValue, result=bool)
    def ipgObjectStore(self, graphUri: str, obj):
        return self.tc(
            self.a_ipgObjectStore,
            graphUri,
            self._dict(obj)
        )

    @pyqtSlot(str, str, str, str, result=bool)
    def tAddLiteral(self, graphUri: str, s, p, o):
        return self.tc(
            self.a_ipgTripleAdd,
            graphUri,
            s, p, Literal(o)
        )

    @pyqtSlot(str, str, str, str, result=bool)
    def tAddUri(self, graphUri: str, s, p, o):
        return self.tc(
            self.a_ipgTripleAdd,
            graphUri,
            s, p, URIRef(o)
        )

    @pyqtSlot(str, str, str, result=str)
    def tGetObjFirst(self, graphUri: str, s, p):
        graph = self.rdfService.graphByUri(graphUri)

        if graph is None:
            return ''

        for o in graph.objects(URIRef(s), URIRef(p)):
            return str(o)

        return ''

    @pyqtSlot(str, result=str)
    def iObjectUriGen(self, oclass):
        return self.iService.iriGenObject(oclass)

    @pyqtSlot(result=bool)
    def ontoloChainCommit(self):
        return True

    @pyqtSlot(QJsonValue, QJsonValue, result=str)
    def ontoloVcStore(self, vc, opts):
        return self.tc(
            self.a_ontoloCreateObject,
            'OntoloChainVCRecord',
            self._dict(vc),
            self._dict(opts)
        )

    @pyqtSlot(QJsonValue, QJsonValue, result=str)
    def ontoloCreateObject(self, obj, opts):
        return self.tc(
            self.a_ontoloCreateObject,
            'OntoloChainRecord',
            self._dict(obj),
            self._dict(opts)
        )

    @pyqtSlot(QJsonValue, QJsonValue, result=str)
    def ontoloCreateObjectAuto(self, data, opts):
        obj = self._dict(data)
        if obj:
            _type = obj.get('@type')
            if not _type:
                return

            oid = self.iService.iriGenObject(_type)
            obj['@id'] = oid

            return self.tc(
                self.a_ontoloCreateObject,
                'OntoloChainRecord',
                obj, self._dict(opts)
            )
