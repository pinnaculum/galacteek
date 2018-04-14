import os

from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtCore import (QStandardPaths, Qt, QEvent, QObject, pyqtSignal,
        QFile)
from PyQt5.QtWidgets import QMessageBox, QWidget, QApplication

from . import galacteek_rc

def getIcon(iconName):
    return QIcon(QPixmap(':/share/icons/{}'.format(iconName)))

def getIconIpfsIce():
    return getIcon('ipfs-logo-128-ice.png')

def getIconIpfsWhite():
    return getIcon('ipfs-logo-128-white.png')

def getHomePath():
    pList = QStandardPaths.standardLocations(QStandardPaths.HomeLocation)
    return pList[0] if len(pList) > 0 else os.getenv('HOME')

def messageBox(message):
    msgBox = QMessageBox()
    msgBox.setText(message)
    msgBox.show()
    return msgBox.exec_()

def runDialog(cls, *args, **kw):
    title = kw.pop('title', None)
    accepted = kw.pop('accepted', None)
    dlgW = cls(*args, **kw)
    def onAccept():
        if accepted:
            accepted(dlgW)
    if title:
        dlgW.setWindowTitle(title)
    if accepted:
        dlgW.accepted.connect(onAccept)
    dlgW.show()
    dlgW.exec_()
    return dlgW

# Key Filter
class KeyFilter(QObject):
    delKeyPressed = pyqtSignal()

    def eventFilter(self,  obj,  event):
        if event.type() == QEvent.KeyPress:
            modifiers = event.modifiers()
        return False

def clipboardSupportsSelection():
    return QApplication.clipboard().supportsSelection()

class BasicKeyFilter(QObject):
    deletePressed = pyqtSignal()
    copyPressed = pyqtSignal()
    returnPressed = pyqtSignal()

    def eventFilter(self,  obj,  event):
        if event.type() == QEvent.KeyPress:
            modifiers = event.modifiers()

            key = event.key()
            if key == Qt.Key_Return:
                self.returnPressed.emit()
            if modifiers & Qt.ControlModifier:
                if key == Qt.Key_C:
                    self.copyPressed.emit()

            if event.key() == Qt.Key_Delete:
                self.deletePressed.emit()
            return True
        return False


