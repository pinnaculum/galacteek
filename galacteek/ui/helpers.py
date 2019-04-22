import os
import functools

from PyQt5.QtGui import QPixmap
from PyQt5.QtGui import QImage
from PyQt5.QtGui import QIcon

from PyQt5.QtCore import QStandardPaths
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QEvent
from PyQt5.QtCore import QObject
from PyQt5.QtCore import QDir
from PyQt5.QtCore import QFile
from PyQt5.QtCore import pyqtSignal

from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QInputDialog
from PyQt5.QtWidgets import QMenu

from galacteek import ensure

from .i18n import iIpfsQrCodes


def getIcon(iconName):
    return QIcon(QPixmap(':/share/icons/{}'.format(iconName)))


def getMimeIcon(mType):
    app = QApplication.instance()
    return app.mimeTypeIcons.get(mType)


def preloadMimeIcons():
    icons = {}
    mIconsDir = QDir(':/share/icons/mimetypes')

    if not mIconsDir.exists():
        return icons

    entries = mIconsDir.entryList()

    for entry in entries:
        mType = entry.replace('.png', '').replace('-', '/', 1)
        icons[mType] = getIcon('mimetypes/{}'.format(entry))

    return icons


async def getIconFromIpfs(ipfsop, ipfsPath, scaleWidth=None):
    try:
        imgData = await ipfsop.waitFor(
            ipfsop.client.cat(ipfsPath), 10
        )

        if not imgData:
            raise Exception('Failed to load image')

        return getIconFromImageData(imgData, scaleWidth=scaleWidth)
    except BaseException:
        return None


def getIconFromImageData(imgData, scaleWidth=None):
    try:
        img = QImage()
        img.loadFromData(imgData)

        if isinstance(scaleWidth, int):
            img = img.scaledToWidth(scaleWidth)

        return QIcon(QPixmap.fromImage(img))
    except BaseException:
        return None


def getIconIpfsIce():
    return getIcon('ipfs-logo-128-ice.png')


def getIconIpfsWhite():
    return getIcon('ipfs-logo-128-white.png')


def getIconIpfs64():
    return getIcon('ipfs-cube-64.png')


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
    return QFileDialog.getExistingDirectory(
        None, caption, getHomePath(), QFileDialog.ShowDirsOnly)


def filesSelect(filter='(*.*)'):
    result = QFileDialog.getOpenFileNames(None,
                                          '', getHomePath(), filter)
    if result:
        return result[0]


def filesSelectImages():
    return filesSelect(
        filter='Images (*.xpm *.jpg *.jpeg *.png *.svg)')


def saveFileSelect(filter='(*.*)'):
    result = QFileDialog.getSaveFileName(None,
                                         '', getHomePath(), filter)
    if result:
        return result[0]


def disconnectSig(sig, target):
    try:
        sig.disconnect(target)
    except Exception:
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
                if key == Qt.Key_C or key == Qt.Key_Y:
                    self.copyHashPressed.emit()
                    return True
                if key == Qt.Key_A:
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

    def eventFilter(self, obj, event):
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
    if size > (1024 * 1024 * 1024):
        return '{0:.2f} Gb'.format(size / (1024 * 1024 * 1024))
    if size > (1024 * 1024):
        return '{0:.2f} Mb'.format(size / (1024 * 1024))
    if size > 1024:
        return '{0:.2f} kb'.format(size / 1024)
    if size == 0:
        return '0'
    return '{0} bytes'.format(size)


def qrCodesMenuBuilder(urls, resourceOpener, parent=None):
    if isinstance(urls, list):
        icon = getIcon('ipfs-qrcode.png')
        menu = QMenu(iIpfsQrCodes(), parent)
        menu.setIcon(icon)

        for url in urls:
            menu.addAction(icon,
                           url, functools.partial(ensure,
                                                  resourceOpener.open(url)))
        return menu


def sampleQrCodes():
    dir = QDir(':/share/qr-codes')
    if dir.exists():
        for entry in dir.entryList():
            yield entry, QFile(':/share/qr-codes/{}'.format(entry))
