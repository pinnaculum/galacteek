
from PyQt5.QtCore import (Qt, QEvent, QObject, pyqtSignal, QFile)
from PyQt5.QtWidgets import QWidget, QApplication

class GalacteekWidget(QWidget):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

class GalacteekTab(QWidget):
    def __init__(self, gWindow, parent=None, **kw):
        super().__init__(parent=parent, **kw)

        self.gWindow = gWindow

    @property
    def app(self):
        return self.gWindow.getApp()
