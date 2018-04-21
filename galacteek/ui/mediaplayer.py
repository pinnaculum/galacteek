
from PyQt5.QtWidgets import (QWidget, QFrame, QApplication, QMainWindow,
        QDialog, QLabel, QTextEdit, QPushButton, QVBoxLayout, QAction,
        QTabWidget, QFileDialog)

from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget, QGraphicsVideoItem
from PyQt5.QtWidgets import QGraphicsScene

from PyQt5.QtCore import QCoreApplication, QUrl, Qt

from . import ui_mediaplayer

from .widgets import *
from .helpers import *

def iPlayerError(code):
    return QCoreApplication.translate('MediaPlayer',
            'Media player error (code: {0})').format(code)

class VideoWidget(QVideoWidget):
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.setFullScreen(False)

        super(VideoWidget, self).keyPressEvent(event)

class MediaPlayerTab(GalacteekTab):
    def __init__(self, *args, **kw):
        super(MediaPlayerTab, self).__init__(*args, **kw)

        self.ui = ui_mediaplayer.Ui_MediaPlayer()
        self.ui.setupUi(self)

        self.player = QMediaPlayer()
        self.currentMedia = None
        self.currentState = None

        self.videoWidget = VideoWidget(parent=self)
        self.videoWidget.show()
        self.ui.verticalLayout.addWidget(self.videoWidget)

        self.player.setVideoOutput(self.videoWidget)

        self.player.error.connect(self.onError)
        self.player.stateChanged.connect(self.onStateChanged)

    def onError(self, error):
        messageBox(iPlayerError(error))

    def onStateChanged(self, state):
        self.currentState = state

    def playFromUrl(self, url):
        if self.currentState == QMediaPlayer.PlayingState:
            self.player.stop()
            self.player.setMedia(QMediaContent(None))

        self.currentMedia = QMediaContent(url)
        self.player.setMedia(self.currentMedia)
        self.player.play()

    def onClose(self):
        self.player.stop()
        self.player.setMedia(QMediaContent(None))
        del self.currentMedia

    def keyPressEvent(self, event):
        modifiers = event.modifiers()
        mSecMove = 3000

        if event.key() == Qt.Key_Space:
            if self.currentState == QMediaPlayer.PlayingState:
                self.player.pause()
            elif self.currentState == QMediaPlayer.PausedState:
                self.player.play()
        if event.key() == Qt.Key_Right:
            pos = self.player.position()
            self.player.setPosition(pos + mSecMove)
        if event.key() == Qt.Key_Up:
            pos = self.player.position()
            self.player.setPosition(pos + mSecMove*2)
        if event.key() == Qt.Key_Left:
            pos = self.player.position()
            if pos > mSecMove:
                self.player.setPosition(pos - mSecMove)
            else:
                self.player.setPosition(0)
        if event.key() == Qt.Key_Down:
            pos = self.player.position()
            if pos > mSecMove*2:
                self.player.setPosition(pos - mSecMove*2)
            else:
                self.player.setPosition(0)
        if event.key() == Qt.Key_F:
            if not self.isFullScreen():
                self.videoWidget.setFullScreen(True)

        super(MediaPlayerTab, self).keyPressEvent(event)
