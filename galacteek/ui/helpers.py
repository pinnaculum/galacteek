import os

from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtCore import (QStandardPaths, Qt, QEvent, QObject, pyqtSignal,
        QFile)
from PyQt5.QtWidgets import (QMessageBox, QWidget, QApplication, QFileDialog,
        QInputDialog)

from . import galacteek_rc

def getIcon(iconName):
    return QIcon(QPixmap(':/share/icons/{}'.format(iconName)))

def getIconIpfsIce():
    return getIcon('ipfs-logo-128-ice.png')

def getIconIpfsWhite():
    return getIcon('ipfs-logo-128-white.png')

def getIconClipboard():
    return getIcon('clipboard.png')

def getHomePath():
    pList = QStandardPaths.standardLocations(QStandardPaths.HomeLocation)
    return pList[0] if len(pList) > 0 else os.getenv('HOME')

def messageBox(message, title=None):
    msgBox = QMessageBox()
    msgBox.setText(message)

    if title:
        msgBox.setWindowTitle(title)

    msgBox.show()
    return msgBox.exec_()

def questionBox(title, text):
    box = QMessageBox.question(None, title, text)
    return box == QMessageBox.Yes

def directorySelect(caption=''):
    return QFileDialog.getExistingDirectory(None,
        caption, getHomePath(), QFileDialog.ShowDirsOnly)

def filesSelect(filter='(*.*)'):
    result = QFileDialog.getOpenFileNames(None,
        '', getHomePath(), filter)
    if result:
        return result[0]

def saveFileSelect(filter='(*.*)'):
    result = QFileDialog.getSaveFileName(None,
        '', getHomePath(), filter)
    if result:
        return result[0]

def disconnectSig(sig, target):
    try:
        sig.disconnect(target)
    except Exception as e:
        pass

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

def inputText(title='', label='', parent=None):
    text, ok = QInputDialog.getText(parent, title, label)
    if ok:
        return text

class IPFSTreeKeyFilter(QObject):
    deletePressed = pyqtSignal()
    copyHashPressed = pyqtSignal()
    copyPathPressed = pyqtSignal()
    explorePressed = pyqtSignal()
    returnPressed = pyqtSignal()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            modifiers = event.modifiers()

            key = event.key()
            if key == Qt.Key_Return:
                self.returnPressed.emit()
                return True
            if modifiers & Qt.ControlModifier:
                if key == Qt.Key_H:
                    self.copyHashPressed.emit()
                    return True
                if key == Qt.Key_P:
                    self.copyPathPressed.emit()
                    return True
                if key == Qt.Key_X:
                    self.explorePressed.emit()
                    return True
            if event.key() == Qt.Key_Delete:
                self.deletePressed.emit()
                return True
        return False

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

def clipboardSupportsSelection():
    return QApplication.clipboard().supportsSelection()

def sizeFormat(size):
    if size > (1024*1024*1024):
        return '{0:.2f} Gb'.format(size/(1024*1024*1024))
    if size > (1024*1024):
        return '{0:.2f} Mb'.format(size/(1024*1024))
    if size > 1024:
        return '{0:.2f} kb'.format(size/1024)
    if size == 0:
        return '0'
    return '{0} bytes'.format(size)
