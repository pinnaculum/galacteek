import functools
import asyncio

from datetime import timedelta

from rdflib import URIRef
from rdflib import RDF
from rdflib import Literal
from rdflib import XSD

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

from PyQt5.QtMultimedia import QMediaPlayer
from PyQt5.QtMultimedia import QMediaContent
from PyQt5.QtMultimedia import QMediaPlaylist
from PyQt5.QtMultimedia import QMultimedia
from PyQt5.QtMultimedia import QAudioProbe
from PyQt5.QtMultimedia import QAudioFormat

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QTime
from PyQt5.QtCore import QItemSelectionModel

from galacteek import partialEnsure
from galacteek import services

from galacteek.core.jsono import *
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ipfs.cidhelpers import joinIpfs
from galacteek.ipfs.cidhelpers import qurlPercentDecode
from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.paths import posixIpfsPath

from galacteek.core.ps import KeyListener
from galacteek.core.ps import keyLdObjects
from galacteek.core.asynclib import asyncWriteFile

from galacteek.core.models.sparql.playlists import *

from galacteek.ld import ipsContextUri
from galacteek.ld import ipsTermUri

from galacteek.ld.rdf import BaseGraph
from galacteek.ld.rdf.resources.multimedia import MultimediaPlaylistResource
from galacteek.ld.rdf.resources.multimedia import MusicRecordingResource
from galacteek.ld.rdf.resources.multimedia import VideoObjectResource
from galacteek.ld.rdf.util import literalDtNow

from .videowidget import MPlayerVideoWidget
from ..forms import ui_mediaplaylist
from ..clipboard import iClipboardEmpty
from ..dialogs import TextBrowserDialog
from ..dialogs import runDialogAsync
from ..widgets import *
from ..widgets.pinwidgets import *
from ..helpers import *


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


def iPlaylistExportToTTL():
    return QCoreApplication.translate(
        'MediaPlayer',
        'Export to Turtle (text/turtle)'
    )


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


def iUnsavedPlaylist():
    return QCoreApplication.translate(
        'MediaPlayer',
        'Unsaved playlist'
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


class QLDMediaPlaylist(QMediaPlaylist):
    def __init__(self, model, parent=None):
        super().__init__(parent)

        self.model = model
        self.rsc = None  # RDF resource


class MediaPlayerTab(GalacteekTab, KeyListener):
    statePlaying = QMediaPlayer.PlayingState
    statePaused = QMediaPlayer.PausedState
    stateStopped = QMediaPlayer.StoppedState

    def __init__(self, gWindow):
        super(MediaPlayerTab, self).__init__(gWindow, sticky=True)

        self.psListen(keyLdObjects)

        self.player = QMediaPlayer(self)
        self.probe = QAudioProbe(self)
        self.probe.audioBufferProbed.connect(self.onAudioBuffer)
        self.playlistIpfsPath = None

        self.model = LDPlayListModel(graph=BaseGraph())
        self.model.playlistChanged.connect(self.onPlaylistChanged)

        self.searchModel = LDPlayListsSearchModel(
            graphUri='urn:ipg:user:multimedia'
        )

        # TODO: deprecate fully, we don't use the playlist API anymore
        self.playlist = QLDMediaPlaylist(self.model, parent=self)

        self.pMenu = QMenu(self)
        self.playlistsMenu = QMenu(iPlaylistLoad(), self.pMenu)
        self.exportMenu = QMenu('Export', self.pMenu)
        self.exportMenu.setIcon(getIcon('multimedia/playlist.png'))

        self.savePlaylistAction = QAction(getIcon('save-file.png'),
                                          iPlaylistSave(), self,
                                          triggered=self.onSavePlaylist)
        self.pinPlaylistAction = QAction(getIcon('pin.png'),
                                         iPlaylistPinItems(), self,
                                         triggered=partialEnsure(
            self.onPinPlaylistMedia))
        self.scanMetadataAction = QAction(getIcon('pin.png'),
                                          'Scan metadata', self,
                                          triggered=partialEnsure(
            self.onScanMetadata))
        self.clearPlaylistAction = QAction(getIcon('clear-all.png'),
                                           iPlaylistClear(), self,
                                           triggered=self.onClearPlaylist)

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
        self.pMenu.addAction(self.scanMetadataAction)
        self.pMenu.addSeparator()

        self.pMenu.addAction(self.copyPathAction)
        self.pMenu.addSeparator()
        # self.pMenu.addAction(self.loadPathAction)
        # self.pMenu.addSeparator()

        self.publishAction = QAction(
            getIcon('multimedia/playlist.png'),
            'Publish', self,
            triggered=partialEnsure(self.onPublishPlaylist)
        )
        self.publishAction.setEnabled(False)

        self.ttlExportAction = QAction(
            getIcon('multimedia/playlist.png'),
            iPlaylistExportToTTL(), self,
            triggered=partialEnsure(self.onExportTTL)
        )

        self.exportMenu.addAction(self.ttlExportAction)

        self.pMenu.addAction(self.publishAction)
        self.pMenu.addMenu(self.exportMenu)

        # self.pMenu.addMenu(self.playlistsMenu)
        # self.playlistsMenu.triggered.connect(self.onPlaylistsMenu)

        self.pListWidget = QWidget(self)
        self.uipList = ui_mediaplaylist.Ui_MediaPlaylist()
        self.uipList.setupUi(self.pListWidget)
        self.uipList.playlistButton.setPopupMode(
            QToolButton.InstantPopup)
        self.uipList.playlistButton.setMenu(self.pMenu)
        self.uipList.queueFromClipboard.clicked.connect(
            partialEnsure(self.onClipboardClicked))
        self.uipList.scanMetadataButton.clicked.connect(
            partialEnsure(self.onScanMetadata))

        self.uipList.clearButton.clicked.connect(self.onClearPlaylist)

        # self.uipList.nextButton.clicked.connect(self.playlistNextMedia)
        # self.uipList.previousButton.clicked.connect(self.playlistPreviousMedia)
        # self.uipList.nextButton.setIcon(getIcon('go-next.png'))
        # self.uipList.previousButton.setIcon(getIcon('go-previous.png'))

        self.uipList.viewPlGraphButton.clicked.connect(
            partialEnsure(self.onViewPlaylistGraph))
        self.uipList.quickSaveButton.clicked.connect(self.onSavePlaylist)

        self.uipList.viewAllPlaylistsButton.clicked.connect(
            self.onViewAllPlaylists)

        self.pListView = self.uipList.listView
        self.pListView.mousePressEvent = self.playlistMousePressEvent
        self.pListView.setModel(self.model)
        self.pListView.setResizeMode(QListView.Adjust)
        self.pListView.setMinimumWidth(self.width() / 2)

        self.uipList.ldSearchView.setModel(self.searchModel)

        self.duration = None
        self.playerState = None

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
        self.player.mediaStatusChanged.connect(self.onMediaStatusChanged)
        # self.player.currentMediaChanged.connect(self.playerMediaChanged)
        self.player.mediaChanged.connect(self.playerMediaChanged)

        self.pListView.activated.connect(self.onListActivated)
        self.pListView.doubleClicked.connect(self.onListActivated)

        self.uipList.ldSearchView.doubleClicked.connect(
            partialEnsure(self.onPlaylistDoubleClicked)
        )

        self.uipList.plSearchLine.textChanged.connect(
            partialEnsure(self.onPlaylistSearch))
        self.uipList.plSearchLine.textEdited.connect(self.onPlaylistSearchEdit)

        self.model.modelReset.connect(self.refreshActions)

        self.togglePList = GLargeToolButton(parent=self)
        self.togglePList.setIcon(getIcon('playlist.png'))
        self.togglePList.setText(iPlaylist())
        self.togglePList.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.togglePList.setCheckable(True)
        self.togglePList.toggled.connect(self.onTogglePlaylist)

        self.clipboardMediaItem = None
        self.clipboardButton.setEnabled(False)

        self.pinButton = PinObjectButton()
        self.pinButton.pinQueueName = 'mplayer'
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

        self.model.newPlaylist()

    @property
    def pronto(self):
        return services.getByDotName('ld.pronto')

    @property
    def graphMultimedia(self):
        return self.pronto.graphByUri('urn:ipg:user:multimedia')

    @property
    def graphPlaylists(self):
        return self.pronto.graphByUri('urn:ipg:user:multimedia:playlists')

    @property
    def graphPlaylistsPublic(self):
        return self.pronto.graphByUri(
            'urn:ipg:user:multimedia:playlists:public')

    @property
    def currentIndex(self):
        return self.pListView.currentIndex()

    @property
    def selModel(self):
        return self.pListView.selectionModel()

    @property
    def clipboardButton(self):
        return self.uipList.queueFromClipboard

    @property
    def mediaCount(self):
        return self.model.rowCount()

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

    @property
    def plGraphIsStandalone(self):
        return self.model.graph.identifier != self.graphPlaylists.identifier

    def useUpdates(self, updates=True):
        # Enable widget updates or not on the video widget
        self.videoWidget.setUpdatesEnabled(updates)

    def update(self):
        self.refreshActions()
        # self.app.task(self.updatePlaylistsMenu)

    def onViewAllPlaylists(self, checked):
        self.uipList.plSearchLine.clear()
        if checked:
            self.uipList.plSearchLine.setText('.*')

    def onPlaylistChanged(self, uri, playlistName: str):
        if playlistName:
            name = str(playlistName)
        else:
            name = iUnsavedPlaylist()

        self.uipList.labelPlName.setText(
            f'<b>{str(name)}</b>')
        self.uipList.labelPlName.setToolTip(str(uri))

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
        currentMedia = self.player.currentMedia()
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

        path = self.model.data(idx, role=MediaIpfsPathRole)
        if path:
            selModel.reset()
            selModel.select(
                idx, QItemSelectionModel.Select
            )

            menu = QMenu(self)
            menu.addAction(
                getIcon('clear-all.png'),
                iPlaylistRemoveMedia(), functools.partial(
                    self.onRemoveMediaFromIndex, idx, IPFSPath(path)))
            menu.exec_(event.globalPos())

    def onRemoveMediaFromIndex(self, idx, iPath: IPFSPath):
        r = self.model.rsc.findByPath(iPath)
        if r:
            self.model.rsc.removeTrack(r)
            ensure(self.model.update())

    def playlistMousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.pListView.selectionModel().reset()
            self.playlistShowContextMenu(event)
        else:
            if not self.pListView.indexAt(event.pos()).isValid():
                self.deselectPlaylistItems()

            QListView.mousePressEvent(self.pListView, event)

    async def onPlaylistDoubleClicked(self, index, *args):
        # When a playlist search result is double-clicked

        uri = self.searchModel.data(index, Qt.UserRole)

        if uri:
            self.uipList.plSearchLine.clear()
            await self.ldPlaylistOpen(URIRef(uri), self.graphPlaylists)

            self.stackViewPlaylist()

    def onPlaylistsMenu(self, action):
        entry = action.data()
        if entry:
            ensure(self.loadPlaylistFromPath(joinIpfs(entry['Hash'])))

    def onSavePlaylist(self):
        cName = self.model.rsc.name

        if not cName:
            listName = inputTextCustom(
                title=iPlaylistName(),
                label=iPlaylistName()
            )

            if not listName:
                return
        else:
            listName = str(cName)

        if not listName:
            return

        if self.model.rsc:
            ensure(self.saveLdPlaylist(self.model.rsc, listName))

    @ipfsOp
    async def saveLdPlaylist(self, ipfsop, rsc, name):
        g = self.model.graph

        g.replace(
            self.model.rsc.identifier,
            ipsTermUri('name'),
            Literal(name, datatype=XSD.string)
        )

        if g.identifier != self.graphPlaylists.identifier:
            await self.graphPlaylists.guardian.mergeReplace(
                g,
                self.graphPlaylists
            )
        else:
            # Playlist is in a pronto graph, no need to do anything
            pass

        self.update()

        self.model.emitPlChanged()

        self.uipList.quickSaveButton.setEnabled(False)
        self.savePlaylistAction.setEnabled(False)

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
            # pList = JSONPlaylistV1(data=obj)
            self.clearPlaylist()

            # for item in pList.items():
            #     self.queueFromPath(item['path'])

            self.playlistIpfsPath = path
            self.copyPathAction.setEnabled(True)
            # self.playlistCurrent = pList
        except Exception:
            return messageBox(iCannotLoadPlaylist())

    async def onScanMetadata(self, *args):
        # Scan metadata for each item
        # Since metadata reading is asynchronous we call asyncio.sleep

        self.uipList.scanMetadataButton.setEnabled(False)
        self.pListView.setEnabled(False)
        selModel = self.pListView.selectionModel()

        for row in range(0, self.mediaCount):
            idx = self.model.createIndex(row, 0)
            media = self.model.mediaForIndex(idx)
            if not media:
                continue

            selModel.clearSelection()
            selModel.select(idx, QItemSelectionModel.Select)

            self.player.setMedia(media)
            await asyncio.sleep(1)

        await self.model.update()

        self.pListView.setEnabled(True)
        self.uipList.scanMetadataButton.setEnabled(True)

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
        self.scanMetadataAction.setEnabled(not self.playlistEmpty)
        self.ttlExportAction.setEnabled(not self.playlistEmpty)

        self.uipList.quickSaveButton.setEnabled(not self.playlistEmpty)
        self.uipList.scanMetadataButton.setEnabled(not self.playlistEmpty)

        self.uipList.quickSaveButton.setVisible(
            self.model.rsc.name is None)

    def playlistGetPaths(self):
        return [u.path() for u in self.playlistGetUrls()]

    def playlistGetUrls(self):
        urls = []
        for row in range(0, self.mediaCount):
            media = self.model.mediaForIndex(
                self.model.createIndex(
                    row,
                    self.currentIndex.column()
                )
            )

            if media:
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
            self.queueFromPath(self.clipboardMediaItem.path)

    def onSliderReleased(self):
        pass

    def playlistViewCurrentChanged(self, current, prev):
        media = self.model.mediaForIndex(self.currentIndex)

        if media:
            self.player.setMedia(media)
            self.player.play()

    def playlistNextMedia(self):
        row = self.currentIndex.row() + 1

        if row < self.mediaCount:
            self.pListView.setCurrentIndex(self.model.createIndex(
                row,
                self.currentIndex.column()
            ))

    def playlistPreviousMedia(self):
        row = self.currentIndex.row() - 1

        if row >= 0:
            self.pListView.setCurrentIndex(self.model.createIndex(
                row,
                self.currentIndex.column()
            ))

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

    def onMediaStatusChanged(self, status):
        if status == QMediaPlayer.EndOfMedia:
            self.playlistNextMedia()

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
            media = self.model.mediaForIndex(index)

            if media:
                self.player.setMedia(media)
                self.player.play()

    def durationAs8601(self, td: timedelta):
        s = td.seconds
        ms = td.microseconds

        if ms != 0:
            ms /= 1000000
            ms = round(ms, 3)
            s += ms

        return 'P{}DT{}S'.format(td.days, s)

    def onMetaData(self):
        # Update metadata in the RDF resource corresponding
        # to the current media played

        if not self.player.isMetaDataAvailable():
            return

        try:
            media = self.player.media()
            if media.isNull() or not self.model.rsc:
                return

            duration = self.player.duration()
            d8601 = self.durationAs8601(
                timedelta(milliseconds=duration)) if duration else None

            p = IPFSPath(media.canonicalUrl().toString())
            if not p.valid:
                return

            track = self.model.rsc.findByPath(p)
            if not track:
                return

            if self.player.isVideoAvailable():
                track.setMediaType(ipsContextUri('VideoObject'))
            elif self.player.isAudioAvailable():
                track.setMediaType(ipsContextUri('MusicRecording'))

            for key in self.player.availableMetaData():
                val = self.player.metaData(key)
                if not val:
                    continue

                track.updateMetadata(key, val)

            if d8601:
                track.updateMetadata('Duration', d8601)

            track.replace(ipsTermUri('dateModified'), literalDtNow())
        except Exception as err:
            log.debug(f'Media metadata update error: {err}')

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

    async def playFromPath(self, path, mediaName=None):
        await self.queueFromPath(path, play=True)

    async def queueFromPath(self, path, playLast=False, mediaName=None,
                            play=False):
        items = [IPFSPath(p) for p in path] if isinstance(path, list) else \
            [IPFSPath(path, autoCidConv=True)]

        self.pListView.setEnabled(False)
        for p in items:
            if not p.valid:
                continue

            r = self.model.rsc.findByPath(p)
            if r:
                # Already in the playlist
                continue

            try:
                mType, stat = await self.app.rscAnalyzer(p.objPath)
                mType, stat = await asyncio.wait_for(
                    self.app.rscAnalyzer(p.objPath),
                    0.3
                )

                dtl = literalDtNow()

                # Always use replace() here, because the media resource
                # could already exist in the graph

                rsc = MusicRecordingResource(self.model.graph, p.ipfsUriRef)

                rsc.replace(ipsTermUri('url'),
                            Literal(p.ipfsUrl, datatype=XSD.string))
                rsc.replace(ipsTermUri('dateCreated'), dtl)
                rsc.replace(ipsTermUri('dateModified'), dtl)

                if mType and mType.isVideo:
                    rsc.replace(RDF.type, ipsContextUri('VideoObject'))
                elif mType and mType.isAudio:
                    rsc.replace(RDF.type, ipsContextUri('MusicRecording'))
                else:
                    rsc.replace(RDF.type, ipsContextUri('MediaObject'))

                if p.basename:
                    # ??
                    rsc.replace(ipsTermUri('name'),
                                Literal(p.basename, datatype=XSD.string))

                self.model.rsc.addTrack(rsc)
            except asyncio.TimeoutError:
                continue
            except Exception:
                continue

        await self.model.update()
        self.pListView.setEnabled(True)

        if playLast or play:
            count = self.playlist.mediaCount()

            if count > 0:
                self.player.stop()
                self.playlist.setCurrentIndex(count - 1)
                self.player.play()

    def clearPlaylist(self):
        self.model.newPlaylist()

        self.playlist.clear()
        self.pListView.reset()
        self.copyPathAction.setEnabled(False)

    def playlistPositionChanged(self, position):
        self.pListView.setCurrentIndex(self.model.index(position, 0))

    def deselectPlaylistItems(self):
        self.pListView.selectionModel().reset()

    def playerMediaChanged(self, media):
        url = media.canonicalUrl()
        iPath = IPFSPath(url.toString())

        self.pinButton.setEnabled(iPath.valid)
        if iPath.valid:
            self.pinButton.changeObject(iPath)

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

    async def event_g_ld_objects(self, key, message):
        iPath, sol, graph = message

        for subj, otype in sol:
            if otype == ipsContextUri('MultimediaPlaylist'):
                playlists = list(graph.subject_predicates(
                    ipsContextUri('MultimediaPlaylist'))
                )

                if len(playlists) == 0:
                    return

                plsuri, _o = playlists.pop()

                await self.ldPlaylistOpen(plsuri, graph)

    async def ldPlaylistOpen(self, plsuri, graph):
        pls = MultimediaPlaylistResource(graph, plsuri)
        if len(pls.track) == 0:
            return

        self.clearPlaylist()

        self.uipList.viewAllPlaylistsButton.setChecked(False)

        self.model.setGraph(graph)
        self.model.attach(pls)

        for trsc in pls.track:
            t = trsc.value(RDF.type)
            if t is None:
                continue

            if t.identifier == ipsContextUri('MusicRecording'):
                record = MusicRecordingResource(graph, trsc.identifier)

                if record.ipfsPath.valid:
                    # self.queueFromPath(record.ipfsPath.objPath)
                    pass
            elif t.identifier == ipsContextUri('VideoObject'):
                vid = VideoObjectResource(graph, trsc.identifier)

                if vid.ipfsPath.valid:
                    # self.queueFromPath(vid.ipfsPath.objPath)
                    pass
            else:
                continue

        await self.model.update()

        self.togglePList.setChecked(True)
        self.app.mainWindow.wspaceMultimedia.wsSwitch()

    def onPlaylistSearchEdit(self, text, *args):
        if text != '':
            self.uipList.viewAllPlaylistsButton.setChecked(False)

    async def onPlaylistSearch(self, text, *args):
        if text != '':
            await self.searchModel.queryPlaylists(text)

            self.stackViewSearches()
        else:
            self.stackViewPlaylist()

    async def onViewPlaylistGraph(self, *args):
        try:
            ttl = await self.model.graph.ttlize()
            dlg = TextBrowserDialog()
            dlg.setPlain(ttl.decode())

            await runDialogAsync(dlg)
        except Exception as err:
            print(str(err))
            pass

    def stackViewPlaylist(self):
        self.uipList.stack.setCurrentIndex(0)

    def stackViewSearches(self):
        self.uipList.stack.setCurrentIndex(1)

    def onAudioBuffer(self, buffer):
        # TODO: visualizer

        if buffer.format().channelCount() != 2:
            return

        if buffer.format().sampleType() == QAudioFormat.SignedInt:
            pass

    async def onExportTTL(self, *args):
        fp = saveFileSelect(filter='(*.ttl)')
        if not fp:
            return

        try:
            r = await self.model.graph.queryAsync(
                '''
                  PREFIX gs: <ips://galacteek.ld/>

                  CONSTRUCT {
                    ?pluri ?p ?o .
                    ?pluri gs:track ?t .
                    ?pluri ?plp ?plo .
                    ?t a ?ttype .
                    ?t gs:name ?name .
                    ?t gs:url ?url .
                    ?t ?tp ?to .
                  } WHERE {
                    ?pluri a gs:MultimediaPlaylist .
                    ?pluri gs:track ?t .
                    ?pluri ?plp ?plo .
                    ?t a ?ttype .
                    ?t gs:name ?name .
                    ?t gs:url ?url .
                    ?t ?tp ?to .
                  }
                ''', initBindings={
                    'pluri': URIRef(self.model.rsc.identifier)
                })

            ttl = r.serialize(
                format='turtle',
                media_type='text/ttl'
            )

            await asyncWriteFile(fp, ttl, mode='w+b')
        except Exception:
            await messageBoxAsync('Export error')

    async def onPublishPlaylist(self, *args):
        await self.graphPlaylistsPublic.guardian.mergeReplace(
            self.model.graph,
            self.graphPlaylistsPublic
        )
