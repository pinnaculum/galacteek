from PyQt5.QtQuick import QQuickItem
from PyQt5.QtQuick import QQuickPaintedItem

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QUrl
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtGui import QPainter


class URLCloudQuickItem(QQuickPaintedItem):
    urlChanged = pyqtSignal(QUrl, QColor)
    urlHovered = pyqtSignal(QUrl, bool)

    cloudClicked = pyqtSignal()
    urlAnimationStartStop = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setRenderTarget(QQuickPaintedItem.FramebufferObject)
        self.setFlag(QQuickItem.ItemHasContents, True)
        self.setFillColor(Qt.transparent)

        self.update()

    @pyqtSlot()
    def cloudClick(self):
        # Called from QML
        self.cloudClicked.emit()

    def urlAnimate(self, animate: bool):
        self.urlAnimationStartStop.emit(animate)
        self.update()

    def urlHoveredAnimate(self, url, animate: bool):
        self.urlHovered.emit(url, animate)
        self.update()

    def changeUrl(self, path: QUrl, color: QColor):
        self.urlChanged.emit(path, color)
        self.update()

    def paint(self, painter: QPainter):
        pass
