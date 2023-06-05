import traceback
from rdflib import URIRef

from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import QJsonValue
from PyQt5.QtCore import QVariant

from galacteek import log
from galacteek.config import cGet
from galacteek.config.util import ocToContainer
from galacteek.core import runningApp
from galacteek.dweb.markdown import markitdown
from galacteek.ipfs.cidhelpers import IPFSPath

from galacteek.ld.rdf import hashmarks as rdf_hashmarks
from galacteek.ld.rdf import tags as rdf_tags

from . import GAsyncObject
from . import opSlot


class GHandler(GAsyncObject):
    @pyqtSlot(result=int)
    def apiVersion(self):
        return 10

    @pyqtSlot(str, str)
    def logMsg(self, level: str, message: str):
        try:
            assert level in ['log', 'warning', 'debug']
            assert len(message) < 256
            getattr(log, level)(f'QML: {message}')
        except Exception:
            pass

    @pyqtSlot(str, result=str)
    def mdToHtml(self, mdText: str):
        try:
            return markitdown(mdText)
        except Exception:
            return ''

    @pyqtSlot(str, QJsonValue, result=str)
    def mdToHtmlWithOpts(self,
                         mdText: str,
                         options: QJsonValue):
        try:
            opts = options.toVariant()
            return markitdown(
                mdText,
                ipfsLinksUseLocalGw=opts.get('ipfsLinksUseLocalGw', False)
            )
        except Exception:
            return ''

    @pyqtSlot(str, result=str)
    def urlFromGateway(self, url: str):
        app = runningApp()

        path = IPFSPath(url)
        if path.valid:
            return path.gwUrlForConnParams(
                app.getIpfsConnectionParams()
            )
        else:
            return ''

    @pyqtSlot(str)
    def setClipboardText(self, text: str):
        try:
            assert isinstance(text, str)
            assert len(text) in range(1, 4096)

            self.app.setClipboardText(text)
        except Exception:
            pass

    @pyqtSlot()
    def getClipboardText(self):
        try:
            return self.app.getClipboardText()
        except Exception:
            return ''

    @pyqtSlot(str, str, QJsonValue, result=QVariant)
    def configGet(self,
                  modName: str,
                  attr: str,
                  default: QJsonValue):
        """
        Wrapper around galacteek.config.cGet
        """
        try:
            cvalue = ocToContainer(cGet(attr, mod=modName))
            assert cvalue
        except Exception:
            return default.toVariant()
        else:
            return QVariant(cvalue)

    @opSlot(str, str, QJsonValue, QJsonValue, result=QVariant)
    async def hashmarksAdd(self,
                           url: str,
                           title: str,
                           itags: QJsonValue,
                           options: QJsonValue):
        """
        Add an RDF hashmark with addLdHashmark()
        """
        extra = {}
        opts = options.toVariant()

        try:
            dstGraph = opts.get('graphUri', None)
            uri = URIRef(url)

            if dstGraph:
                extra['graphUri'] = dstGraph

            result = await rdf_hashmarks.addLdHashmark(
                uri,
                title,
                **extra
            )

            assert result is True

            for tag in itags.toVariant():
                rdf_hashmarks.ldHashmarkTag(uri, URIRef(tag), **extra)

            if opts.get('watchTags') is True:
                for tag in itags.toVariant():
                    rdf_tags.tagWatch(URIRef(tag))

            return QVariant(True)
        except Exception:
            log.warning(f'hashmarksAdd error: {traceback.format_exc()}')

            return QVariant(False)
