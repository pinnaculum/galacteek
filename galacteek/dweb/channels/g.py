from PyQt5.QtCore import pyqtSlot

from galacteek.dweb.markdown import markitdown

from . import AsyncChanObject


class GHandler(AsyncChanObject):
    @pyqtSlot(str, result=str)
    def mdToHtml(self, mdText: str):
        try:
            return markitdown(mdText)
        except Exception:
            return ''
