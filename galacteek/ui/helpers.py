import os

from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtCore import (QStandardPaths, Qt, QEvent, QObject, pyqtSignal,
        QFile)
from PyQt5.QtWidgets import QMessageBox, QWidget

from . import galacteek_rc

def getIcon(iconName):
    return QIcon(QPixmap(':/share/icons/{}'.format(iconName)))

def getHomePath():
    pList = QStandardPaths.standardLocations(QStandardPaths.HomeLocation)
    return pList[0] if len(pList) > 0 else os.getenv('HOME')

def messageBox(message):
    msgBox = QMessageBox()
    msgBox.setText(message)
    msgBox.show()
    return msgBox.exec_()

# Key Filter
class KeyFilter(QObject):
    delKeyPressed = pyqtSignal()

    def eventFilter(self,  obj,  event):
        if event.type() == QEvent.KeyPress:
            modifiers = event.modifiers()
        return False

class GalacteekWidget(QWidget):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
