import functools

from PyQt5.QtCore import Qt
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QTimer
from PyQt5.QtMultimediaWidgets import QVideoWidget


class MPlayerVideoWidget(QVideoWidget):
    pauseRequested = pyqtSignal()

    def __init__(self, player, parent=None):
        super(MPlayerVideoWidget, self).__init__(parent)
        self.player = player

    def keyPressEvent(self, event):
        mSecMove = 3000
        pos = self.player.position()

        if event.key() == Qt.Key_Escape:
            self.viewFullScreen(False)
        if event.key() in [Qt.Key_Space, Qt.Key_P]:
            self.pauseRequested.emit()
        if event.key() == Qt.Key_Right:
            self.player.setPosition(pos + mSecMove)
        if event.key() == Qt.Key_Left:
            pos = self.player.position()
            if pos > mSecMove:
                self.player.setPosition(pos - mSecMove)
            else:
                self.player.setPosition(0)

        if event.key() == Qt.Key_Up:
            pos = self.player.position()
            self.player.setPosition(pos + mSecMove * 2)

        if event.key() == Qt.Key_Down:
            pos = self.player.position()
            if pos > mSecMove * 2:
                self.player.setPosition(pos - mSecMove * 2)
            else:
                self.player.setPosition(0)
        if event.key() == Qt.Key_F:
            self.viewFullScreen(not self.isFullScreen())

        super(MPlayerVideoWidget, self).keyPressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.viewFullScreen(not self.isFullScreen())
        super(MPlayerVideoWidget, self).mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        self.changeFocus()
        super(MPlayerVideoWidget, self).mousePressEvent(event)

    def viewFullScreen(self, fullscreen):
        self.setFullScreen(fullscreen)
        if fullscreen:
            self.setCursor(Qt.BlankCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

        self.changeFocus()

    def changeFocus(self):
        QTimer.singleShot(0, functools.partial(self.setFocus,
                                               Qt.OtherFocusReason))
