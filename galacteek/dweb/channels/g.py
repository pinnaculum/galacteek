from PyQt5.QtCore import pyqtSlot

from galacteek.core import runningApp
from galacteek.dweb.markdown import markitdown
from galacteek.ipfs.cidhelpers import IPFSPath

from . import GAsyncObject


class GHandler(GAsyncObject):
    @pyqtSlot(result=int)
    def apiVersion(self):
        return 1

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
