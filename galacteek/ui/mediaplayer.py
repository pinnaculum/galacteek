
from PyQt5.QtWidgets import (QWidget, QFrame, QApplication, QMainWindow,
        QDialog, QLabel, QTextEdit, QPushButton, QVBoxLayout, QAction,
        QHBoxLayout, QTabWidget, QFileDialog, QListView, QSplitter,
        QToolButton, QStyle, QSlider, QGraphicsScene)

from PyQt5.QtMultimedia import (QMediaPlayer, QMediaContent, QMediaPlaylist,
    QMediaMetaData)
from PyQt5.QtMultimediaWidgets import QVideoWidget, QGraphicsVideoItem

from PyQt5.QtCore import (QCoreApplication, QUrl, Qt, QAbstractItemModel,
    QModelIndex, QTime)

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

def durationConvert(duration):
    return QTime((duration/3600)%60, (duration/60)%60,
        duration%60, (duration*1000)%1000)

class MediaPlayerTab(GalacteekTab):
    def __init__(self, *args, **kw):
        super(MediaPlayerTab, self).__init__(*args, **kw)

        self.ui = ui_mediaplayer.Ui_MediaPlayer()
        self.ui.setupUi(self)

        self.playlist = QMediaPlaylist()
        self.model = ListModel(self.playlist)
        self.pListView = QListView()
        self.pListView.setModel(self.model)
        self.pListView.setResizeMode(QListView.Adjust)
        self.pListView.setMinimumWidth(500)

        self.duration = None
        self.currentState = None
        self.player = QMediaPlayer()
        self.player.setPlaylist(self.playlist)

        self.videoWidget = VideoWidget()

        self.player.setVideoOutput(self.videoWidget)

        self.player.error.connect(self.onError)
        self.player.stateChanged.connect(self.onStateChanged)
        self.player.metaDataChanged.connect(self.onMetaData)
        self.playlist.currentIndexChanged.connect(self.playlistPositionChanged)
        self.player.durationChanged.connect(self.mediaDurationChanged)
        self.player.positionChanged.connect(self.mediaPositionChanged)
        self.pListView.activated.connect(self.onListActivated)

        self.togglePList = QToolButton()
        self.togglePList.setIcon(self.style().standardIcon(QStyle.SP_ArrowRight))
        self.togglePList.setFixedSize(32, 128)
        self.togglePList.clicked.connect(self.onTogglePlaylist)

        self.clipboardButton = QToolButton(clicked=self.onClipboardClicked)
        self.clipboardButton.setIcon(getIcon('clipboard-with-pencil-.png'))
        self.clipboardButton.setEnabled(self.app.clipTracker.hasIpfs)
        self.app.clipTracker.clipboardHasIpfs.connect(self.onClipboardIpfs)

        self.playButton = QToolButton(clicked=self.onPlayClicked)
        self.playButton.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

        self.pauseButton = QToolButton(clicked=self.onPauseClicked)
        self.pauseButton.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        self.pauseButton.setEnabled(False)

        self.stopButton = QToolButton(clicked=self.onStopClicked)
        self.stopButton.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.stopButton.setEnabled(False)

        self.seekSlider = QSlider(Qt.Horizontal, sliderMoved=self.onSeek)
        self.durationLabel = QLabel()

        vLayout = QVBoxLayout()
        hLayoutControls = QHBoxLayout()
        hLayoutControls.setContentsMargins(0, 0, 0, 0)
        hLayoutControls.addWidget(self.clipboardButton)
        hLayoutControls.addWidget(self.playButton)
        hLayoutControls.addWidget(self.pauseButton)
        hLayoutControls.addWidget(self.stopButton)
        hLayoutControls.addWidget(self.seekSlider)
        hLayoutControls.addWidget(self.durationLabel)
        vLayout.addWidget(self.videoWidget)
        vLayout.addLayout(hLayoutControls)

        hLayout = QHBoxLayout()
        hLayout.addLayout(vLayout)
        hLayout.addWidget(self.pListView)
        hLayout.addWidget(self.togglePList)

        self.pListView.hide()

        self.ui.verticalLayout.addLayout(hLayout)

    def onClipboardIpfs(self, valid, cid, path):
        self.clipboardButton.setEnabled(valid)
        self.clipboardButton.setToolTip(path)

    def onClipboardClicked(self):
        current = self.app.clipTracker.getCurrent()
        if current:
            self.playFromPath(current['path'])

    def onPlayClicked(self):
        self.player.play()

    def onPauseClicked(self):
        if self.currentState == QMediaPlayer.PlayingState:
            self.player.pause()
        elif self.currentState == QMediaPlayer.PausedState:
            self.player.play()

    def onStopClicked(self):
        self.player.stop()
        self.player.setPosition(0)
        self.seekSlider.setValue(0)
        self.seekSlider.setRange(0, 0)

    def onSeek(self, seconds):
        self.player.setPosition(seconds * 1000)

    def onTogglePlaylist(self):
        if self.pListView.isHidden():
            self.pListView.show()
        else:
            self.pListView.hide()

    def onError(self, error):
        messageBox(iPlayerError(error))

    def onStateChanged(self, state):
        self.currentState = state
        self.updateControls(state)

    def updateControls(self, state):
        if state == QMediaPlayer.StoppedState:
            self.stopButton.setEnabled(False)
            self.pauseButton.setEnabled(False)
            self.playButton.setEnabled(True)
            self.seekSlider.setEnabled(False)
            self.duration = None
        elif state == QMediaPlayer.PlayingState:
            self.seekSlider.setRange(0, self.player.duration() / 1000)
            self.seekSlider.setEnabled(True)
            self.pauseButton.setEnabled(True)
            self.playButton.setEnabled(False)
            self.stopButton.setEnabled(True)

    def onListActivated(self, index):
        if index.isValid():
            self.playlist.setCurrentIndex(index.row())
            self.player.play()

    def onMetaData(self):
        # Unfinished
        if self.player.isMetaDataAvailable():
            availableKeys = self.player.availableMetaData()

            for key in availableKeys:
                value = self.player.metaData(key)

    def playFromUrl(self, url, mediaName=None):
        if self.currentState == QMediaPlayer.PlayingState:
            self.player.stop()

        media = QMediaContent(url)
        self.playlist.addMedia(media)
        self.playlist.next()
        self.player.play()

    def playFromPath(self, path, mediaName=None):
        mediaUrl = QUrl('{0}{1}'.format(self.app.gatewayUrl, path))
        self.playFromUrl(mediaUrl)

    def clearPlaylist(self):
        self.playlist.clear()

    def playlistPositionChanged(self, position):
        self.pListView.setCurrentIndex(self.model.index(position, 0))

    def mediaDurationChanged(self, duration):
        duration /= 1000
        self.duration = duration
        self.seekSlider.setMaximum(duration)

    def mediaPositionChanged(self, progress):
        progress /= 1000

        if self.duration:
            cTime = durationConvert(progress)
            tTime = durationConvert(self.duration)
            self.durationLabel.setText('{0} ({1})'.format(
                cTime.toString(), tTime.toString()))

        if not self.seekSlider.isSliderDown():
            self.seekSlider.setValue(progress)

    def onClose(self):
        self.player.stop()
        self.player.setMedia(QMediaContent(None))
        return True

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
            self.videoWidget.setFullScreen(True)

        super(MediaPlayerTab, self).keyPressEvent(event)

class ListModel(QAbstractItemModel):
    def __init__(self, playlist, parent=None):
        super(ListModel, self).__init__(parent)
        self.playlist = playlist
        self.playlist.mediaAboutToBeInserted.connect(
                self.beginInsertItems)
        self.playlist.mediaInserted.connect(self.endInsertItems)
        self.playlist.mediaChanged.connect(self.changeItems)

    def rowCount(self, parent=QModelIndex()):
        return self.playlist.mediaCount()

    def columnCount(self, parent=QModelIndex()):
        return 1 if not parent.isValid() else 0

    def index(self, row, column, parent=QModelIndex()):
        return self.createIndex(row, column)

    def parent(self, child):
        return QModelIndex()

    def beginInsertItems(self, start, end):
        self.beginInsertRows(QModelIndex(), start, end)

    def endInsertItems(self):
        self.endInsertRows()

    def changeItems(self, start, end):
        self.dataChanged.emit(self.index(start, 0), self.index(end, 1))

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid() and role == Qt.DisplayRole:
            if index.column() == 0:
                media = self.playlist.media(index.row())
                location = media.canonicalUrl()
                return location.path()
            return self.m_data[index]
        return None
