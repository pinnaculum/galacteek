
from PyQt5.QtCore import (Qt, QEvent, QObject, pyqtSignal, QFile)
from PyQt5.QtWidgets import QWidget, QApplication

from galacteek.ipfs.wrappers import ipfsOp

class GalacteekTab(QWidget):
    def __init__(self, gWindow, parent=None, **kw):
        super().__init__(parent=parent)

        self.gWindow = gWindow

    def onClose(self):
        return True

    @ipfsOp
    async def initialize(self, op):
        pass

    @property
    def app(self):
        return self.gWindow.app

    @property
    def loop(self):
        return self.app.loop

    @property
    def profile(self):
        return self.app.ipfsCtx.currentProfile
