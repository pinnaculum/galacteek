import posixpath
import functools

from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QListView
from PyQt5.QtWidgets import QToolButton
from PyQt5.QtWidgets import QSlider
from PyQt5.QtWidgets import QMenu
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtGui import QFont

from PyQt5.QtMultimedia import QMediaPlayer
from PyQt5.QtMultimedia import QMediaContent
from PyQt5.QtMultimedia import QMediaPlaylist
from PyQt5.QtMultimedia import QMultimedia

from PyQt5.QtMultimediaWidgets import QVideoWidget

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import Qt
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QAbstractItemModel
from PyQt5.QtCore import QModelIndex
from PyQt5.QtCore import QTime
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import QItemSelectionModel

from galacteek import partialEnsure

from galacteek.core.jsono import *
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ipfs.cidhelpers import joinIpfs
from galacteek.ipfs.cidhelpers import qurlPercentDecode
from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.paths import posixIpfsPath

from .forms import ui_mediaplaylist

from .clipboard import iClipboardEmpty
from .widgets import *
from .widgets.pinwidgets import *
from .helpers import *


def iPlayerUnavailable():
    return QCoreApplication.translate(
        'MediaPlayer',
        'No media player support available on your system')


def iPlayerError(code):
    return QCoreApplication.translate(
        'MediaPlayer',
        'Media player error (code: {0})').format(code)


def iFullScreen():
    return QCoreApplication.translate('MediaPlayer', 'Fullscreen')


def iCopyPlaylistPath():
    return QCoreApplication.translate(
        'MediaPlayer',
        "Copy playlist's IPFS path to the clipboard")


def iLoadPlaylistFromPath():
    return QCoreApplication.translate(
        'MediaPlayer',
        'Load playlist from the clipboard')


def iCannotLoadPlaylist():
    return QCoreApplication.translate('MediaPlayer',
                                      'Cannot load playlist')


def iPlaylistExists():
    return QCoreApplication.translate(
        'MediaPlayer',
        'A playlist with this name already exists')


def iPlaylistRemoveMedia():
    return QCoreApplication.translate(
        'MediaPlayer',
        'Remove media from playlist')


def iPlaylist():
    return QCoreApplication.translate(
        'MediaPlayer',
        'Playlist'
    )


def iPlaylistName():
    return QCoreApplication.translate(
        'MediaPlayer',
        'Playlist name')


def iPlaylistPinItems():
    return QCoreApplication.translate(
        'MediaPlayer',
        'Pin playlist items'
    )


def iPlaylistClear():
    return QCoreApplication.translate(
        'MediaPlayer',
        'Clear playlist'
    )


def iPlaylistSave():
    return QCoreApplication.translate(
        'MediaPlayer',
        'Save playlist'
    )


def iPlaylistLoad():
    return QCoreApplication.translate(
        'MediaPlayer',
        'Load playlist'
    )


def iAlreadyInPlaylist():
    return QCoreApplication.translate('MediaPlayer',
                                      'Already queued in the current playlist')


def iNoMediaInPlaylist():
    return QCoreApplication.translate(
        'MediaPlayer', 'No media in playlist')


def mediaPlayerAvailable(player=None):
    if player is None:
        player = QMediaPlayer()
    availability = player.availability()
    return availability == QMultimedia.Available


def durationConvert(duration):
    return QTime((duration / 3600) % 60, (duration / 60) % 60,
                 duration % 60, (duration * 1000) % 1000)


class JSONPlaylistV1(QJSONObj):
    """
    V1 JSON playlist document
    """

    def prepare(self, root):
        root['playlist'] = {
            'name': self.listName,
            'formatv': 1,
            'items': []
        }

        for path in self.itemPaths:
            root['playlist']['items'].append({
                'path': path
            })
        self.changed.emit()

    def items(self):
        return self.root['playlist']['items']

    @property
    def name(self):
        try:
            return self.root['playlist']['name']
        except Exception:
            return None


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


class MediaPlayerTab(GalacteekTab):
    statePlaying = QMediaPlayer.PlayingState
    statePaused = QMediaPlayer.PausedState
    stateStopped = QMediaPlayer.StoppedState

    def __init__(self, gWindow):
        super(MediaPlayerTab, self).__init__(gWindow, sticky=True)

        self.playlistCurrent = None
        self.playlistIpfsPath = None
        self.playlist = QMediaPlaylist()
        self.model = ListModel(self.playlist)

        self.pMenu = QMenu(self)
        self.playlistsMenu = QMenu(iPlaylistLoad(), self.pMenu)

        self.savePlaylistAction = QAction(getIcon('save-file.png'),
                                          iPlaylistSave(), self,
                                          triggered=self.onSavePlaylist)
        self.pinPlaylistAction = QAction(getIcon('pin.png'),
                                         iPlaylistPinItems(), self,
                                         triggered=partialEnsure(
            self.onPinPlaylistMedia))
        self.clearPlaylistAction = QAction(getIcon('clear-all.png'),
                                           iPlaylistClear(), self,
                                           triggered=self.onClearPlaylist)
        self.savePlaylistAction.setEnabled(False)
        self.copyPathAction = QAction(getIconIpfsIce(),
                                      iCopyPlaylistPath(), self,
                                      triggered=self.onCopyPlaylistPath)
        self.copyPathAction.setEnabled(False)
        self.loadPathAction = QAction(getIconIpfsIce(),
                                      iLoadPlaylistFromPath(), self,
                                      triggered=self.onLoadPlaylistPath)

        self.pMenu.addAction(self.clearPlaylistAction)
        self.pMenu.addSeparator()
        self.pMenu.addAction(self.savePlaylistAction)
        self.pMenu.addSeparator()
        self.pMenu.addAction(self.pinPlaylistAction)
        self.pMenu.addSeparator()

        self.pMenu.addAction(self.copyPathAction)
        self.pMenu.addSeparator()
        self.pMenu.addAction(self.loadPathAction)
        self.pMenu.addSeparator()

        self.pMenu.addMenu(self.playlistsMenu)

        self.playlistsMenu.triggered.connect(self.onPlaylistsMenu)

        self.pListWidget = QWidget(self)
        self.uipList = ui_mediaplaylist.Ui_MediaPlaylist()
        self.uipList.setupUi(self.pListWidget)
        self.uipList.playlistButton.setPopupMode(
            QToolButton.InstantPopup)
        self.uipList.playlistButton.setMenu(self.pMenu)
        self.uipList.queueFromClipboard.clicked.connect(
            partialEnsure(self.onClipboardClicked))

        self.uipList.clearButton.clicked.connect(self.onClearPlaylist)

        self.uipList.nextButton.clicked.connect(self.onPlaylistNext)
        self.uipList.previousButton.clicked.connect(self.onPlaylistPrevious)
        self.uipList.nextButton.setIcon(getIcon('go-next.png'))
        self.uipList.previousButton.setIcon(getIcon('go-previous.png'))

        self.pListView = self.uipList.listView
        self.pListView.mousePressEvent = self.playlistMousePressEvent
        self.pListView.setModel(self.model)
        self.pListView.setResizeMode(QListView.Adjust)
        self.pListView.setMinimumWidth(self.width() / 2)

        self.duration = None
        self.playerState = None
        self.player = QMediaPlayer(self)
        self.player.setPlaylist(self.playlist)

        self.videoWidget = MPlayerVideoWidget(self.player, self)
        self.useUpdates(True)
        self.videoWidget.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.videoWidget.pauseRequested.connect(
            self.onPauseClicked
        )

        self.player.setVideoOutput(self.videoWidget)

        self.player.error.connect(self.onError)
        self.player.stateChanged.connect(self.onStateChanged)
        self.player.metaDataChanged.connect(self.onMetaData)
        self.player.durationChanged.connect(self.mediaDurationChanged)
        self.player.positionChanged.connect(self.mediaPositionChanged)
        self.player.videoAvailableChanged.connect(self.onVideoAvailable)

        self.pListView.activated.connect(self.onListActivated)
        self.playlist.currentIndexChanged.connect(self.playlistPositionChanged)
        self.playlist.currentMediaChanged.connect(self.playlistMediaChanged)
        self.playlist.mediaInserted.connect(self.playlistMediaInserted)
        self.playlist.mediaRemoved.connect(self.playlistMediaRemoved)

        self.togglePList = GLargeToolButton(parent=self)
        self.togglePList.setIcon(getIcon('playlist.png'))
        self.togglePList.setText(iPlaylist())
        self.togglePList.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.togglePList.setCheckable(True)
        self.togglePList.toggled.connect(self.onTogglePlaylist)

        self.clipboardMediaItem = None
        self.clipboardButton.setEnabled(False)

        self.pinButton = PinObjectButton()
        self.pinButton.setEnabled(False)

        # self.processClipboardItem(self.app.clipTracker.current, force=True)
        self.app.clipTracker.currentItemChanged.connect(self.onClipItemChange)

        self.playButton = GMediumToolButton(
            parent=self, clicked=self.onPlayClicked)
        self.playButton.setIcon(getIcon('mplayer/play.png'))

        self.pauseButton = GMediumToolButton(
            parent=self, clicked=self.onPauseClicked)
        self.pauseButton.setIcon(getIcon('mplayer/pause.png'))
        self.pauseButton.setEnabled(False)

        self.stopButton = GMediumToolButton(
            parent=self, clicked=self.onStopClicked)
        self.stopButton.setIcon(getIcon('mplayer/stop.png'))
        self.stopButton.setEnabled(False)

        self.fullscreenButton = GMediumToolButton(
            parent=self, clicked=self.onFullScreen)
        self.fullscreenButton.setIcon(getIcon('fullscreen.png'))
        self.fullscreenButton.setToolTip(iFullScreen())

        self.seekSlider = QSlider(Qt.Horizontal, sliderMoved=self.onSeek)
        self.seekSlider.sliderReleased.connect(self.onSliderReleased)
        self.seekSlider.setObjectName('mediaPlayerSlider')
        self.durationLabel = QLabel()

        vLayout = QVBoxLayout()
        hLayoutControls = QHBoxLayout()
        hLayoutControls.setContentsMargins(4, 4, 4, 4)
        hLayoutControls.addWidget(self.togglePList)
        hLayoutControls.addWidget(self.pinButton)
        hLayoutControls.addWidget(self.playButton)
        hLayoutControls.addWidget(self.pauseButton)
        hLayoutControls.addWidget(self.stopButton)
        hLayoutControls.addWidget(self.seekSlider)
        hLayoutControls.addWidget(self.durationLabel)
        hLayoutControls.addWidget(self.fullscreenButton)
        vLayout.addWidget(self.videoWidget)
        vLayout.addLayout(hLayoutControls)

        hLayout = QHBoxLayout()
        hLayout.addLayout(vLayout)
        hLayout.addWidget(self.pListWidget)

        self.pListWidget.hide()

        self.vLayout.addLayout(hLayout)
        self.update()
        self.videoWidget.changeFocus()

    @property
    def clipboardButton(self):
        return self.uipList.queueFromClipboard

    @property
    def mediaCount(self):
        return self.playlist.mediaCount()

    @property
    def playlistEmpty(self):
        return self.mediaCount == 0

    @property
    def isPlaying(self):
        return self.playerState == self.statePlaying

    @property
    def isPaused(self):
        return self.playerState == self.statePaused

    @property
    def isStopped(self):
        return self.playerState == self.stateStopped

    def useUpdates(self, updates=True):
        # Enable widget updates or not on the video widget
        self.videoWidget.setUpdatesEnabled(updates)

    def update(self):
        self.refreshActions()
        self.app.task(self.updatePlaylistsMenu)

    def onFullScreen(self):
        self.videoWidget.viewFullScreen(True)

    def onClearPlaylist(self):
        self.copyPathAction.setEnabled(False)
        self.player.stop()
        self.clearPlaylist()

    def onLoadPlaylistPath(self):
        current = self.app.clipTracker.getCurrent()
        if current:
            self.app.task(self.loadPlaylistFromPath, current.path)

    def onCopyPlaylistPath(self):
        if self.playlistIpfsPath:
            self.app.setClipboardText(self.playlistIpfsPath)

    def onPinMediaClicked(self):
        currentMedia = self.playlist.currentMedia()
        if currentMedia.isNull():
            return messageBox(iNoMediaInPlaylist())

        ensure(self.pinMedia(currentMedia))

    @ipfsOp
    async def pinMedia(self, ipfsop, media):
        mediaUrl = qurlPercentDecode(media.canonicalUrl())
        path = IPFSPath(mediaUrl, autoCidConv=True)

        if path.valid:
            await ipfsop.ctx.pin(str(path), qname='mediaplayer')

    @ipfsOp
    async def updatePlaylistsMenu(self, ipfsop):
        def actionForName(name):
            for action in self.playlistsMenu.actions():
                if action.text() == name:
                    return action

        listing = await ipfsop.filesList(self.profile.pathPlaylists)

        for entry in listing:
            eAction = actionForName(entry['Name'])
            if eAction:
                eAction.setData(entry)
                continue

            action = QAction(entry['Name'], self)
            action.setIcon(getIcon('playlist.png'))
            action.setData(entry)

            self.playlistsMenu.addAction(action)

    def playlistShowContextMenu(self, event):
        selModel = self.pListView.selectionModel()
        idx = self.pListView.indexAt(event.pos())
        if not idx.isValid():
            return

        path = self.model.data(idx)
        if path:
            selModel.reset()
            selModel.select(
                idx, QItemSelectionModel.Select
            )

            menu = QMenu(self)
            menu.addAction(
                getIcon('clear-all.png'),
                iPlaylistRemoveMedia(), functools.partial(
                    self.onRemoveMediaFromIndex, idx))
            menu.exec_(event.globalPos())

    def onRemoveMediaFromIndex(self, idx):
        self.playlist.removeMedia(idx.row())

    def playlistMousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.pListView.selectionModel().reset()
            self.playlistShowContextMenu(event)
        else:
            if not self.pListView.indexAt(event.pos()).isValid():
                self.deselectPlaylistItems()

            QListView.mousePressEvent(self.pListView, event)

    def onPlaylistsMenu(self, action):
        entry = action.data()
        if entry:
            ensure(self.loadPlaylistFromPath(joinIpfs(entry['Hash'])))

    def onSavePlaylist(self):
        paths = self.playlistGetPaths()

        currentPl = self.playlistCurrent
        if currentPl:
            listName = currentPl.name
        else:
            listName = inputText(title=iPlaylistName(), label=iPlaylistName())

        if not listName:
            return

        obj = JSONPlaylistV1(listName=listName, itemPaths=paths)
        ensure(self.savePlaylist(obj, listName))

    @ipfsOp
    async def savePlaylist(self, ipfsop, obj, name):
        objPath = posixIpfsPath.join(self.profile.pathPlaylists, name)
        exists = await ipfsop.filesStat(objPath)

        if exists:
            await ipfsop.filesRm(objPath)

        ent = await ipfsop.client.core.add_json(obj.root)

        if ent:
            await ipfsop.filesLinkFp(ent, objPath)
            self.playlistIpfsPath = joinIpfs(ent['Hash'])
            self.copyPathAction.setEnabled(True)

        self.update()

    @ipfsOp
    async def loadPlaylistFromPath(self, ipfsop, path):
        try:
            obj = await ipfsop.jsonLoad(path)
        except Exception:
            return messageBox(iCannotLoadPlaylist())

        if obj is None:
            return messageBox(iCannotLoadPlaylist())

        try:
            # Assume v1 format for now, when the format evolves we'll just
            # use json validation
            pList = JSONPlaylistV1(data=obj)
            self.clearPlaylist()

            for item in pList.items():
                self.queueFromPath(item['path'])

            self.playlistIpfsPath = path
            self.copyPathAction.setEnabled(True)
            self.playlistCurrent = pList
        except Exception:
            return messageBox(iCannotLoadPlaylist())

    @ipfsOp
    async def onPinPlaylistMedia(self, ipfsop, *args):
        """
        Pin each media in the playlist
        """
        for path in self.playlistGetPaths():
            await ipfsop.ctx.pin(
                path, recursive=False, qname='mediaplayer')

    def refreshActions(self):
        self.pinPlaylistAction.setEnabled(not self.playlistEmpty)
        self.savePlaylistAction.setEnabled(not self.playlistEmpty)

    def playlistMediaInserted(self, start, end):
        self.refreshActions()

    def playlistMediaRemoved(self, start, end):
        self.refreshActions()

        self.model.modelReset.emit()

    def playlistGetPaths(self):
        return [u.path() for u in self.playlistGetUrls()]

    def playlistGetUrls(self):
        urls = []
        for idx in range(0, self.mediaCount):
            media = self.playlist.media(idx)
            urls.append(media.canonicalUrl())
        return urls

    def onClipItemChange(self, item):
        ensure(self.processClipboardItem(item))

    async def processClipboardItem(self, item, force=False):
        if not item:
            return

        def analyzeMimeType(cItem):
            if cItem.mimeCategory in ['audio', 'video', 'image']:
                self.clipboardMediaItem = cItem
                self.clipboardButton.setEnabled(True)
                self.clipboardButton.setToolTip(cItem.path)
            elif cItem.mimeType.isDir:
                self.clipboardMediaItem = cItem
                self.clipboardButton.setEnabled(True)
                self.clipboardButton.setToolTip(cItem.path)
            else:
                self.clipboardButton.setEnabled(False)
                self.clipboardButton.setToolTip(iClipboardEmpty())
        if force:
            analyzeMimeType(item)
        else:
            item.mimeTypeAvailable.connect(
                lambda mType: analyzeMimeType(item))

    @ipfsOp
    async def onClipboardClicked(self, ipfsop, *args):
        if not self.clipboardMediaItem:
            # messageBox('Not a multimedia object')
            return

        if self.clipboardMediaItem.mimeType.isDir:
            # Queue from directory
            async for objPath, parent in ipfsop.walk(
                    str(self.clipboardMediaItem.path)):
                self.queueFromPath(objPath)
        else:
            self.playFromPath(self.clipboardMediaItem.path)

    def onSliderReleased(self):
        pass

    def onPlaylistNext(self):
        self.playlist.next()

    def onPlaylistPrevious(self):
        self.playlist.previous()

    def onPlayClicked(self):
        self.player.play()

    def onPauseClicked(self):
        if self.isPlaying:
            self.player.pause()
        elif self.isPaused:
            self.player.play()

    def onStopClicked(self):
        self.player.stop()
        self.player.setPosition(0)
        self.seekSlider.setValue(0)
        self.seekSlider.setRange(0, 0)

    def onSeek(self, seconds):
        if self.player.isSeekable():
            self.player.setPosition(seconds * 1000)

    def showEvent(self, event):
        if self.playlistEmpty:
            self.togglePList.setChecked(True)

        super().showEvent(event)

    def onTogglePlaylist(self, checked):
        self.togglePlaylist(checked)

    def togglePlaylist(self, show):
        self.pListWidget.setVisible(show)

    def onError(self, error):
        if error == QMediaPlayer.ResourceError:
            msg = iMediaPlayerResourceError()
        elif error == QMediaPlayer.FormatError:
            msg = iMediaPlayerUnsupportedFormatError()
        elif error == QMediaPlayer.NetworkError:
            msg = iMediaPlayerNetworkError()
        else:
            msg = None

        if msg:
            messageBox(msg)

    def onStateChanged(self, state):
        self.playerState = state
        self.updateControls(state)

    def updateControls(self, state):
        if self.isStopped:
            self.stopButton.setEnabled(False)
            self.pauseButton.setEnabled(False)
            self.playButton.setEnabled(True)
            self.seekSlider.setEnabled(False)
            self.duration = None
        elif self.isPaused:
            self.stopButton.setEnabled(True)
            self.pauseButton.setEnabled(False)
            self.playButton.setEnabled(True)
            self.seekSlider.setEnabled(False)
        elif self.isPlaying:
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
                self.player.metaData(key)

    def playFromUrl(self, url, mediaName=None):
        if self.isPlaying:
            self.player.stop()

        cUrls = self.playlistGetUrls()
        for u in cUrls:
            if u.toString() == url.toString():
                return messageBox(iAlreadyInPlaylist())

        media = QMediaContent(url)
        if self.playlist.addMedia(media):
            count = self.model.rowCount()
            if count > 0:
                self.playlist.setCurrentIndex(count - 1)

        self.player.play()

    def playFromPath(self, path, mediaName=None):
        mediaUrl = self.app.subUrl(path)
        self.playFromUrl(mediaUrl)

    def queueFromPath(self, path, playLast=False, mediaName=None):
        mediaUrl = self.app.subUrl(path)
        self.playlist.addMedia(QMediaContent(mediaUrl))

        if playLast:
            count = self.playlist.mediaCount()

            if count > 0:
                self.player.stop()
                self.playlist.setCurrentIndex(count - 1)
                self.player.play()

    def clearPlaylist(self):
        self.playlist.clear()
        self.pListView.reset()
        self.playlistCurrent = None
        self.copyPathAction.setEnabled(False)

    def playlistPositionChanged(self, position):
        self.pListView.setCurrentIndex(self.model.index(position, 0))

    def deselectPlaylistItems(self):
        self.pListView.selectionModel().reset()

    def playlistMediaChanged(self, media):
        media = self.playlist.currentMedia()
        if media.isNull():
            return

        url = media.canonicalUrl()
        iPath = IPFSPath(url.toString())

        self.pinButton.setEnabled(iPath.valid)
        if iPath.valid:
            self.pinButton.changeObject(iPath)

        selModel = self.pListView.selectionModel()

        self.deselectPlaylistItems()

        self.model.modelReset.emit()
        idx = self.model.index(self.playlist.currentIndex(), 0)

        if idx.isValid():
            selModel.select(idx, QItemSelectionModel.Select)

    def onVideoAvailable(self, available):
        if available:
            if self.isPlaying:
                self.useUpdates(False)
            elif self.isStopped or self.isPaused:
                self.useUpdates(True)
        else:
            self.useUpdates(True)

    def mediaDurationChanged(self, duration):
        self.duration = duration / 1000
        self.seekSlider.setMaximum(self.duration)

    def mediaPositionChanged(self, progress):
        progress /= 1000

        if self.duration:
            cTime = durationConvert(progress)
            tTime = durationConvert(self.duration)
            self.durationLabel.setText('{0} ({1})'.format(
                cTime.toString(), tTime.toString()))

        if not self.seekSlider.isSliderDown():
            self.seekSlider.setValue(progress)

    async def onClose(self):
        self.player.stop()
        self.player.setMedia(QMediaContent(None))
        return True

    def playerAvailable(self):
        return mediaPlayerAvailable(player=self.player)


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

    def basenameForIndex(self, index):
        if index.column() == 0:
            media = self.playlist.media(index.row())
            if media is None:
                return iUnknown()
            location = media.canonicalUrl()
            path = location.path()
            basename = posixpath.basename(path)

            if basename:
                return basename
            else:
                return path

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return

        if role == Qt.DisplayRole:
            if index.column() == 0:
                media = self.playlist.media(index.row())
                if media is None:
                    return iUnknown()
                location = media.canonicalUrl()
                path = location.path()
                basename = posixpath.basename(path)
                if basename:
                    return basename
                else:
                    return path
            return self.m_data[index]
        elif role == Qt.ToolTipRole:
            return self.basenameForIndex(index)
        elif role == Qt.FontRole and 0:
            curPlIndex = self.playlist.currentIndex()

            font = QFont('Times', pointSize=12)

            if curPlIndex == index.row():
                font = QFont('Times', pointSize=14)
                font.setBold(True)
                return font
            else:
                return QFont('Times', pointSize=12)

        return None
