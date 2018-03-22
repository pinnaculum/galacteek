
from PyQt5.QtWidgets import (QWidget, QFrame, QApplication, QMainWindow,
        QDialog, QLabel, QTextEdit, QPushButton, QVBoxLayout, QAction,
        QTabWidget, QFileDialog)

from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget, QGraphicsVideoItem
from PyQt5.QtWidgets import QGraphicsScene

from PyQt5.QtCore import QCoreApplication, QUrl, Qt

from . import ui_mediaplayer

class MediaPlayerTab(QWidget):
    def __init__(self, parent = None):
        super(QWidget, self).__init__(parent = parent)

        self.ui = ui_mediaplayer.Ui_MediaPlayer()
        self.ui.setupUi(self)

        self.player = QMediaPlayer()
        self.currentMedia = None
        self.currentState = None

        self.videoWidget = QVideoWidget(parent = self)
        self.videoWidget.show()
        self.ui.verticalLayout.addWidget(self.videoWidget)

        self.player.setVideoOutput(self.videoWidget)

        self.player.error.connect(self.onError)
        self.player.stateChanged.connect(self.onStateChanged)

    def onError(self, error):
        pass

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
        if event.key() == Qt.Key_Left:
            pos = self.player.position()
            if pos > mSecMove:
                self.player.setPosition(pos - mSecMove)
