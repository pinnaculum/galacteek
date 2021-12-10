from PyQt5.QtCore import pyqtSlot

from galacteek import log
from galacteek.core import runningApp
from galacteek.dweb.markdown import markitdown
from galacteek.ipfs.cidhelpers import IPFSPath

from . import GAsyncObject


class GHandler(GAsyncObject):
    @pyqtSlot(result=int)
    def apiVersion(self):
        return 4

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
