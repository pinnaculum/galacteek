from PyQt5.QtCore import pyqtSlot

from galacteek.dweb.markdown import markitdown

from . import AsyncChanObject


class GHandler(AsyncChanObject):
    @pyqtSlot(result=int)
    def apiVersion(self):
        return 1

    @pyqtSlot(str, result=str)
    def mdToHtml(self, mdText: str):
        try:
            return markitdown(mdText)
        except Exception:
            return ''
