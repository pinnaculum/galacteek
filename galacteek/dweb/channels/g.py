from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import QJsonValue
from PyQt5.QtCore import QVariant

from galacteek import log
from galacteek.config import cGet
from galacteek.config.util import ocToContainer
from galacteek.core import runningApp
from galacteek.dweb.markdown import markitdown
from galacteek.ipfs.cidhelpers import IPFSPath

from . import GAsyncObject


class GHandler(GAsyncObject):
    @pyqtSlot(result=int)
    def apiVersion(self):
        return 8

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
