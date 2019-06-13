import functools
import os.path

from logbook import Handler
from logbook import StringFormatterHandlerMixin

from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QToolBar
from PyQt5.QtWidgets import QMenu
from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QActionGroup
from PyQt5.QtWidgets import QToolButton
from PyQt5.QtWidgets import QInputDialog
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QLabel

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import QDateTime
from PyQt5.QtCore import QSize
from PyQt5.QtCore import QPoint

from PyQt5.Qt import QSizePolicy

from PyQt5.QtGui import QKeySequence

from PyQt5 import QtWebEngineWidgets

from galacteek import ensure, log
from galacteek.core.glogger import loggerUser
from galacteek.core.glogger import easyFormatString
from galacteek.core.asynclib import asyncify
from galacteek.ui import mediaplayer
from galacteek.ipfs.wrappers import *
from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ipfs.cidhelpers import joinIpns
from galacteek.ipfs.cidhelpers import shortPathRepr

from galacteek.core.orbitdb import GalacteekOrbitConnector
from galacteek.dweb.page import HashmarksPage, DWebView, WebTab
from galacteek.core.modelhelpers import *

from . import ui_galacteek
from . import ui_ipfsinfos

from . import userwebsite
from . import browser
from . import files
from . import keys
from . import settings
from . import orbital
from . import textedit
from . import ipfsview
from . import ipfssearch
from . import peers
from . import eventlog
from . import pin
from . import chat

from .textedit import TextEditorTab
from .pyramids import MultihashPyramidsToolBar
from .quickaccess import QuickAccessToolBar
from .helpers import *
from .widgets import PopupToolButton
from .widgets import HashmarkMgrButton
from .widgets import HashmarksLibraryButton
from .dialogs import *
from ..appsettings import *
from .i18n import *

from .clipboard import ClipboardManager
from .clipboard import ClipboardItemsStack


def iPinningItemStatus(pinPath, pinProgress):
    return QCoreApplication.translate(
        'GalacteekWindow',
        '\nPath: {0}, nodes processed: {1}').format(pinPath, pinProgress)


def iAbout():
    from galacteek import __version__
    return QCoreApplication.translate('GalacteekWindow', '''
        <p>
        <b>Galacteek</b> is a multi-platform Qt5-based IPFS browser
        </p>
        <p>Author: David Ferlier</p>
        <p>Contact:
            <a href="mailto:
            galacteek@protonmail.com">galacteek@protonmail.com</a>
        </p>
        <p>Galacteek version {0}</p>''').format(__version__)


class MainWindowLogHandler(Handler, StringFormatterHandlerMixin):
    """
    Custom logbook handler that logs to the status bar

    Should be moved to a separate module
    """

    def __init__(self, application_name=None, address=None,
                 facility='user', level=0, format_string=None,
                 filter=None, bubble=False, window=None):
        Handler.__init__(self, level, filter, bubble)
        StringFormatterHandlerMixin.__init__(self, format_string)
        self.application_name = application_name
        self.window = window
        self.format_string = easyFormatString

    def emit(self, record):
        self.window.statusMessage(self.format(record))


class IPFSInfosDialog(QDialog):
    """
    IPFS node/repository information dialog
    """

    def __init__(self, app, parent=None):
        super().__init__(parent)

        self.ui = ui_ipfsinfos.Ui_IPFSInfosDialog()
        self.ui.setupUi(self)
        self.ui.okButton.clicked.connect(functools.partial(self.done, 1))

        self.labels = [self.ui.repoObjCount,
                       self.ui.repoVersion,
                       self.ui.repoSize,
                       self.ui.repoMaxStorage,
                       self.ui.nodeId,
                       self.ui.agentVersion,
                       self.ui.protocolVersion]

        self.enableLabels(False)

    def enableLabels(self, enable):
        for label in self.labels:
            if not enable:
                label.setText('Fetching ...')

            label.setEnabled(enable)

    @ipfsOp
    async def loadInfos(self, ipfsop):
        try:
            repoStat = await ipfsop.client.repo.stat()
            idInfo = await ipfsop.client.core.id()
        except BaseException:
            for label in self.labels:
                label.setText(iUnknown())
        else:
            self.ui.repoObjCount.setText(str(repoStat.get(
                'NumObjects', iUnknown())))
            self.ui.repoVersion.setText(str(repoStat.get(
                'Version', iUnknown())))
            self.ui.repoSize.setText(sizeFormat(repoStat.get(
                'RepoSize', 0)))
            self.ui.repoMaxStorage.setText(sizeFormat(repoStat.get(
                'StorageMax', 0)))

            self.ui.nodeId.setText(idInfo.get('ID', iUnknown()))
            self.ui.agentVersion.setText(idInfo.get(
                'AgentVersion', iUnknown()))
            self.ui.protocolVersion.setText(idInfo.get('ProtocolVersion',
                                                       iUnknown()))
            self.enableLabels(True)


class DatabasesManager(QObject):
    def __init__(self, orbitConnector, parent=None):
        super().__init__(parent)

        self.mainW = parent

        self.icon = getIcon('orbitdb.png')
        self.connector = orbitConnector
        self._dbButton = self.buildButton()

    @property
    def button(self):
        return self._dbButton

    def buildButton(self):
        dbButton = QToolButton()
        dbButton.setIconSize(QSize(24, 24))
        dbButton.setIcon(self.icon)
        dbButton.setPopupMode(QToolButton.MenuButtonPopup)

        self.databasesMenu = QMenu()
        self.mainFeedAction = QAction(self.icon,
                                      'General discussions feed', self,
                                      triggered=self.onMainFeed)
        self.databasesMenu.addAction(self.mainFeedAction)
        dbButton.setMenu(self.databasesMenu)
        return dbButton

    def onMainFeed(self):
        database = self.connector.database('feeds', 'general')
        view = orbital.OrbitFeedView(self.connector, database,
                                     parent=self.mainW.ui.tabWidget)
        self.mainW.registerTab(view, 'General', current=True,
                               icon=self.icon)


class MiscToolBar(QToolBar):
    moved = pyqtSignal(int)

    def __init__(self, parent):
        super().__init__(parent)

        self.setObjectName('toolbarMisc')
        self.setAllowedAreas(
            Qt.RightToolBarArea
        )
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def contextMenuEvent(self, event):
        # no context menu
        pass


class MainToolBar(QToolBar):
    moved = pyqtSignal(int)

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName('toolbarMain')

        self.setFloatable(False)
        self.setAllowedAreas(
            Qt.LeftToolBarArea | Qt.TopToolBarArea
        )
        self.setContextMenuPolicy(Qt.NoContextMenu)

        # Empty widget
        self.emptySpace = QWidget()
        self.emptySpace.setSizePolicy(
            QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.lastPos = None

    @property
    def vertical(self):
        return self.orientation() == Qt.Vertical

    @property
    def horizontal(self):
        return self.orientation() == Qt.Horizontal

    def dragEnterEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        pass


class ProfileButton(PopupToolButton):
    pass


class TabWidgetKeyFilter(QObject):
    nextPressed = pyqtSignal()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            modifiers = event.modifiers()

            key = event.key()
            if modifiers & Qt.ControlModifier:
                if key == Qt.Key_J:
                    self.nextPressed.emit()
                    return True
        return False


class MainWindow(QMainWindow):
    def __init__(self, app):
        super(MainWindow, self).__init__()

        self.showMaximized()
        self._app = app
        self._allTabs = []
        self._lastFeedMark = None

        self.ui = ui_galacteek.Ui_GalacteekWindow()
        self.ui.setupUi(self)

        self.menuBar().hide()

        loggerUser.handlers.append(
            MainWindowLogHandler(window=self, level='DEBUG'))

        self.tabnFManager = iFileManager()
        self.tabnKeys = iKeys()
        self.tabnPinning = iPinningStatus()
        self.tabnMediaPlayer = iMediaPlayer()
        self.tabnHashmarks = iHashmarks()
        self.tabnChat = iChat()

        self.ui.actionCloseAllTabs.triggered.connect(
            self.onCloseAllTabs)
        self.ui.actionSettings.triggered.connect(
            self.onSettings)
        self.ui.actionEvent_log.triggered.connect(
            self.onOpenEventLog)

        self.actionQuit = QAction(
            getIcon('quit.png'),
            'Exit', self,
            shortcut=QKeySequence('Ctrl+q'),
            triggered=self.quit)

        self.menuManual = QMenu(iManual())

        # Global pin-all button
        self.pinAllGlobalButton = QToolButton()
        self.pinAllGlobalButton.setIcon(getIcon('pin.png'))
        self.pinAllGlobalButton.setObjectName('pinGlobalButton')
        self.pinAllGlobalButton.setToolTip(iGlobalAutoPinning())
        self.pinAllGlobalButton.setCheckable(True)
        self.pinAllGlobalButton.setAutoRaise(True)
        self.pinAllGlobalChecked = False
        self.pinAllGlobalButton.toggled.connect(self.onToggledPinAllGlobal)
        self.pinAllGlobalButton.setChecked(self.app.settingsMgr.browserAutoPin)

        self.toolbarMain = MainToolBar(self)
        self.toolbarPyramids = MultihashPyramidsToolBar(self)

        self.toolbarMain.orientationChanged.connect(self.onMainToolbarMoved)
        self.toolbarTools = QToolBar()
        self.toolbarTools.setOrientation(self.toolbarMain.orientation())

        # Apps/shortcuts toolbar
        self.qaToolbar = QuickAccessToolBar(self)
        self.qaToolbar.setOrientation(self.toolbarMain.orientation())

        # Browse button
        self.browseButton = QToolButton()
        self.browseButton.setPopupMode(QToolButton.MenuButtonPopup)
        self.browseButton.setObjectName('buttonBrowseIpfs')
        self.browseButton.clicked.connect(self.onOpenBrowserTabClicked)
        menu = QMenu()
        menu.addAction(getIconIpfsIce(), 'Browse',
                       self.onOpenBrowserTabClicked)
        menu.addAction(getIconIpfsIce(), 'Browse (auto-pin)',
                       functools.partial(self.onOpenBrowserTabClicked,
                                         pinBrowsed=True)
                       )
        self.browseButton.setMenu(menu)
        self.browseButton.setIcon(getIconIpfs64())

        # File manager button
        self.fileManagerButton = QToolButton()
        self.fileManagerButton.setToolTip(iFileManager())
        self.fileManagerButton.setIcon(getIcon('folder-open.png'))
        self.fileManagerButton.clicked.connect(self.onFileManagerClicked)
        self.fileManagerButton.setShortcut(QKeySequence('Ctrl+f'))

        # File manager
        self.fileManagerWidget = files.FileManager(parent=self)

        # Text editor button
        self.textEditorButton = QToolButton()
        self.textEditorButton.setToolTip(iTextEditor())
        self.textEditorButton.setIcon(getIcon('text-editor.png'))
        self.textEditorButton.clicked.connect(self.addEditorTab)

        # Edit-Profile button
        self.menuUserProfile = QMenu()
        self.menuUserProfile.addSeparator()
        self.menuUserProfile.triggered.connect(self.onUserProfile)
        self.profilesActionGroup = QActionGroup(self)

        # Profile button
        self.profileMenu = QMenu()
        iconProfile = getIcon('profile-user.png')
        self.profileMenu.addAction(iconProfile,
                                   'Edit profile',
                                   self.onProfileEditDialog)
        self.profileMenu.addAction(getIcon('go-home.png'),
                                   'View homepage',
                                   self.onProfileViewHomepage)
        self.profileMenu.addSeparator()

        self.userWebsiteManager = userwebsite.UserWebsiteManager(
            parent=self.profileMenu)
        self.profileMenu.addMenu(self.userWebsiteManager.blogMenu)

        self.profileEditButton = ProfileButton(
            menu=self.profileMenu,
            mode=QToolButton.InstantPopup,
            icon=iconProfile
        )
        self.profileEditButton.setEnabled(False)

        # Hashmarks mgr button
        self.hashmarkMgrButton = HashmarkMgrButton(
            marks=self.app.marksLocal)
        self.hashmarkMgrButton.setShortcut(QKeySequence('Ctrl+m'))
        self.hashmarkMgrButton.menu.addAction(getIcon('hashmarks.png'),
                                              iHashmarksManager(),
                                              self.addHashmarksTab)
        self.hashmarkMgrButton.menu.addSeparator()
        self.hashmarkMgrButton.updateMenu()

        # Shared hashmarks mgr button
        self.sharedHashmarkMgrButton = HashmarksLibraryButton()
        self.sharedHashmarkMgrButton.setToolTip(iSharedHashmarks())

        # Peers button
        self.peersButton = QToolButton()
        self.peersButton.setIcon(getIcon('peers.png'))
        self.peersButton.clicked.connect(self.onPeersMgrClicked)

        self.clipboardItemsStack = ClipboardItemsStack(parent=self.toolbarMain)

        # Clipboard loader button
        self.clipboardManager = ClipboardManager(
            self.app.clipTracker,
            self.clipboardItemsStack,
            self.app.resourceOpener,
            icon=getIcon('clipboard.png'),
            parent=self.toolbarMain
        )

        # Settings button
        settingsIcon = getIcon('settings.png')
        self.settingsToolButton = QToolButton()
        self.settingsToolButton.setIcon(settingsIcon)
        self.settingsToolButton.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu()
        menu.addAction(settingsIcon, iSettings(),
                       self.onSettings)
        menu.addSeparator()
        menu.addAction(settingsIcon, iEventLog(),
                       self.onOpenEventLog)
        menu.addAction(getIcon('lock-and-key.png'), iKeys(),
                       self.onIpfsKeysClicked)
        self.settingsToolButton.setMenu(menu)

        self.helpToolButton = QToolButton()
        self.helpToolButton.setIcon(getIcon('information.png'))
        self.helpToolButton.setPopupMode(QToolButton.MenuButtonPopup)
        self.helpToolButton.clicked.connect(
            functools.partial(self.onOpenManual, 'en'))
        menu = QMenu()
        menu.addMenu(self.menuManual)
        menu.addAction('Donate', self.onHelpDonate)
        menu.addAction('About', self.onAboutGalacteek)
        self.helpToolButton.setMenu(menu)

        self.ipfsSearchButton = ipfssearch.IPFSSearchButton()
        self.ipfsSearchButton.hovered.connect(
            functools.partial(self.toggleIpfsSearchWidget, True))
        self.ipfsSearchButton.setShortcut(QKeySequence('Ctrl+s'))
        self.ipfsSearchButton.setIcon(self.ipfsSearchButton.iconNormal)
        self.ipfsSearchButton.toggled.connect(self.toggleIpfsSearchWidget)

        self.ipfsSearchWidget = ipfssearch.IPFSSearchWidget(self)
        self.ipfsSearchWidget.runSearch.connect(self.addIpfsSearchView)
        self.ipfsSearchWidget.hidden.connect(
            functools.partial(self.ipfsSearchButton.setChecked, False))

        self.mPlayerButton = QToolButton()
        self.mPlayerButton.setIcon(getIcon('multimedia.png'))
        self.mPlayerButton.setToolTip(iMediaPlayer())
        self.mPlayerButton.clicked.connect(self.onOpenMediaPlayer)

        self.toolbarMain.addWidget(self.browseButton)
        self.toolbarMain.addWidget(self.hashmarkMgrButton)
        self.toolbarMain.addWidget(self.sharedHashmarkMgrButton)

        self.toolbarMain.addSeparator()
        self.toolbarMain.addWidget(self.fileManagerButton)
        self.toolbarMain.addWidget(self.textEditorButton)

        self.hashmarkMgrButton.hashmarkClicked.connect(self.onHashmarkClicked)
        self.sharedHashmarkMgrButton.hashmarkClicked.connect(
            self.onHashmarkClicked)

        self.toolbarMain.addWidget(self.mPlayerButton)
        self.toolbarMain.addSeparator()

        self.toolbarMain.addWidget(self.toolbarTools)
        self.toolbarMain.addSeparator()
        self.toolbarMain.addWidget(self.qaToolbar)

        self.toolbarTools.addWidget(self.peersButton)
        self.toolbarTools.addWidget(self.profileEditButton)

        self.toolbarMain.actionStatuses = self.toolbarMain.addAction(
            'Statuses')
        self.toolbarMain.actionStatuses.setVisible(False)

        self.toolbarMain.addWidget(self.toolbarMain.emptySpace)
        self.toolbarMain.addSeparator()
        self.toolbarMain.addWidget(self.ipfsSearchButton)
        self.toolbarMain.addSeparator()
        self.toolbarMain.addWidget(self.clipboardItemsStack)
        self.toolbarMain.addWidget(self.clipboardManager)
        self.toolbarMain.addSeparator()

        self.toolbarMain.addWidget(self.pinAllGlobalButton)
        self.toolbarMain.addWidget(self.settingsToolButton)

        self.toolbarMain.addWidget(self.helpToolButton)
        self.toolbarMain.addAction(self.actionQuit)

        self.addToolBar(Qt.TopToolBarArea, self.toolbarMain)
        self.addToolBar(Qt.RightToolBarArea, self.toolbarPyramids)

        self.ui.tabWidget.setDocumentMode(True)
        self.ui.tabWidget.setTabsClosable(True)
        self.ui.tabWidget.tabCloseRequested.connect(self.onTabCloseRequest)
        self.ui.tabWidget.setElideMode(Qt.ElideMiddle)
        self.ui.tabWidget.setUsesScrollButtons(True)

        tabKeyFilter = TabWidgetKeyFilter(self)
        tabKeyFilter.nextPressed.connect(self.cycleTabs)
        self.ui.tabWidget.installEventFilter(tabKeyFilter)

        # Chat room
        self.chatRoomWidget = chat.ChatRoomWidget(self)
        self.chatRoomButton = QToolButton()
        self.chatRoomButton.setIcon(getIcon('chat.png'))
        self.chatRoomButton.clicked.connect(self.onOpenChatWidget)
        self.toolbarTools.addWidget(self.chatRoomButton)

        self.webProfile = QtWebEngineWidgets.QWebEngineProfile.defaultProfile()

        # Status bar setup
        self.ui.pinningStatusButton = QPushButton()
        self.ui.pinningStatusButton.setToolTip(iNoStatus())
        self.ui.pinningStatusButton.setIcon(getIcon('pin-black.png'))
        self.ui.pinningStatusButton.clicked.connect(
            self.showPinningStatusWidget)
        self.ui.pubsubStatusButton = QPushButton()
        self.ui.pubsubStatusButton.setIcon(getIcon('network-offline.png'))
        self.ui.ipfsInfosButton = QPushButton()
        self.ui.ipfsInfosButton.setIcon(getIcon('information.png'))
        self.ui.ipfsInfosButton.setToolTip(iIpfsInfos())
        self.ui.ipfsInfosButton.clicked.connect(self.onIpfsInfos)

        self.ui.ipfsStatusLabel = QLabel()
        self.ui.statusbar.addPermanentWidget(self.ui.ipfsStatusLabel)
        self.ui.statusbar.addPermanentWidget(self.ui.ipfsInfosButton)
        self.ui.statusbar.addPermanentWidget(self.ui.pinningStatusButton)
        self.ui.statusbar.addPermanentWidget(self.ui.pubsubStatusButton)

        # Connection status timer
        self.timerStatus = QTimer(self)
        self.timerStatus.timeout.connect(self.onMainTimerStatus)
        self.timerStatus.start(20000)

        self.enableButtons(False)

        # Connect the IPFS context signals
        self.app.ipfsCtx.ipfsConnectionReady.connect(self.onConnReady)
        self.app.ipfsCtx.ipfsRepositoryReady.connect(self.onRepoReady)
        self.app.ipfsCtx.pubsub.psMessageRx.connect(self.onPubsubRx)
        self.app.ipfsCtx.pubsub.psMessageTx.connect(self.onPubsubTx)
        self.app.ipfsCtx.profilesAvailable.connect(self.onProfilesList)
        self.app.ipfsCtx.profileChanged.connect(self.onProfileChanged)
        self.app.ipfsCtx.pinItemStatusChanged.connect(self.onPinStatusChanged)
        self.app.ipfsCtx.pinItemsCount.connect(self.onPinItemsCount)
        self.app.ipfsCtx.pinFinished.connect(self.onPinFinished)

        # Misc signals
        self.app.marksLocal.feedMarkAdded.connect(self.onFeedMarkAdded)
        self.app.systemTray.messageClicked.connect(self.onSystrayMsgClicked)

        # Application signals
        self.app.manualAvailable.connect(self.onManualAvailable)

        self.ui.tabWidget.removeTab(0)

        previousGeo = self.app.settingsMgr.mainWindowGeometry
        if previousGeo:
            self.restoreGeometry(previousGeo)
        previousState = self.app.settingsMgr.mainWindowState
        if previousState:
            self.restoreState(previousState)

        self.hashmarksPage = None
        self.pinStatusTab = pin.PinStatusWidget(self)

        self.pinIconLoading = getIcon('pin-blue-loading.png')
        self.pinIconNormal = getIcon('pin-black.png')

    @property
    def app(self):
        return self._app

    @property
    def allTabs(self):
        return self._allTabs

    def cycleTabs(self):
        curIndex = self.ui.tabWidget.currentIndex()
        if curIndex + 1 < self.ui.tabWidget.count():
            self.ui.tabWidget.setCurrentIndex(curIndex + 1)
        else:
            self.ui.tabWidget.setCurrentIndex(0)

    def onHashmarkClicked(self, path, title):
        ipfsPath = IPFSPath(path)

        if ipfsPath.valid:
            ensure(self.app.resourceOpener.open(ipfsPath))

    def onMainToolbarMoved(self, orientation):
        self.toolbarMain.lastPos = self.toolbarMain.pos()

        self.toolbarTools.setOrientation(orientation)
        self.qaToolbar.setOrientation(orientation)

        if self.toolbarMain.vertical:
            self.toolbarMain.emptySpace.setSizePolicy(
                QSizePolicy.Minimum, QSizePolicy.Expanding)
            self.qaToolbar.setMinimumHeight(
                self.toolbarMain.height() / 3)
            self.qaToolbar.setMinimumWidth(32)
        elif self.toolbarMain.horizontal:
            self.qaToolbar.setMinimumWidth(
                self.width() / 3)
            self.qaToolbar.setMinimumHeight(32)
            self.toolbarMain.emptySpace.setSizePolicy(QSizePolicy.Expanding,
                                                      QSizePolicy.Minimum)

    def onOpenEventLog(self):
        self.addEventLogTab(current=True)

    def onProfileEditDialog(self):
        runDialog(ProfileEditDialog, self.app.ipfsCtx.currentProfile,
                  title='Profile Edit dialog')

    def onProfileWebsiteUpdated(self):
        self.profileEditButton.setStyleSheet('''
            QToolButton {
                background-color: #B7CDC2;
            }
        ''')
        self.app.loop.call_later(
            3, self.profileEditButton.setStyleSheet,
            'QToolButton {}'
        )

    def onProfileInfoChanged(self, profile):
        # Regen website
        ensure(profile.userWebsite.update())

    @asyncify
    async def onProfileChanged(self, pName, profile):
        if not profile.initialized:
            return

        def hashmarksLoaded(hmarks):
            try:
                self.sharedHashmarkMgrButton.updateMenu(hmarks)
            except Exception as err:
                log.debug(str(err))

        profile.sharedHManager.hashmarksLoaded.connect(hashmarksLoaded)

        self.profileEditButton.setEnabled(False)
        await profile.userInfo.loaded
        self.profileEditButton.setEnabled(True)

        if profile.userWebsite:
            profile.userWebsite.websiteUpdated.connect(
                self.onProfileWebsiteUpdated
            )

        profile.userInfo.changed.connect(
            lambda: self.onProfileInfoChanged(profile)
        )

        for action in self.profilesActionGroup.actions():
            if action.data() == pName:
                action.setChecked(True)
                # Refresh the file manager
                filesM = self.findTabFileManager()
                if filesM:
                    filesM.setupModel()
                    filesM.pathSelectorDefault()

    def onUserProfile(self, action):
        if action is self.ui.actionNew_Profile:
            inText = QInputDialog.getText(self, iNewProfile(),
                                          iNewProfile())
            profile, create = inText
            if create is True and profile:
                self.app.task(self.app.ipfsCtx.profileNew, profile,
                              emitavail=True)
        else:
            pName = action.text()
            if action.isChecked() and \
                    self.app.ipfsCtx.currentProfile.name != pName:
                self.app.ipfsCtx.profileChange(pName)

    def onProfileViewHomepage(self):
        self.addBrowserTab().browseFsPath(os.path.join(
            joinIpns(self.app.ipfsCtx.currentProfile.keyRootId), 'index.html'))

    def onProfilesList(self, pList):
        currentList = [action.data() for action in
                       self.profilesActionGroup.actions()]

        for pName in pList:
            if pName in currentList:
                continue

            action = QAction(self.profilesActionGroup,
                             checkable=True, text=pName)
            action.setData(pName)

        for action in self.profilesActionGroup.actions():
            self.menuUserProfile.addAction(action)

    def onRepoReady(self):
        self.enableButtons()

        ensure(self.displayConnectionInfo())
        ensure(self.qaToolbar.init())
        ensure(self.hashmarkMgrButton.updateIcons())
        ensure(self.app.marksLocal.pyramidsInit())

        if self.app.enableOrbital and self.app.ipfsCtx.orbitConnector is None:
            self.app.ipfsCtx.orbitConnector = GalacteekOrbitConnector(
                orbitDataPath=self.app.orbitDataLocation,
                servicePort=self.app.settingsMgr.getSetting(
                    CFG_SECTION_ORBITDB,
                    CFG_KEY_CONNECTOR_LISTENPORT
                )
            )
            ensure(self.orbitStart())

    @ipfsOp
    async def orbitStart(self, ipfsop):
        resp = await self.app.ipfsCtx.orbitConnector.start()

        if resp:
            orbitIcon = QPushButton()
            orbitIcon.setIcon(getIcon('orbitdb.png'))
            orbitIcon.setToolTip('OrbitDB: connected')
            self.ui.statusbar.addPermanentWidget(orbitIcon)

            self.orbitManager = DatabasesManager(
                self.app.ipfsCtx.orbitConnector, self)
            self.toolbarTools.addWidget(self.orbitManager.button)

            await ipfsop.ctx.currentProfile.orbitalSetup(
                self.app.ipfsCtx.orbitConnector)

    def onSystrayMsgClicked(self):
        # Open last shown mark in the systray
        if self._lastFeedMark is not None:
            self.addBrowserTab().browseFsPath(self._lastFeedMark.path)

    def onFeedMarkAdded(self, feedname, mark):
        self._lastFeedMark = mark

        metadata = mark.markData.get('metadata', None)
        if not metadata:
            return

        message = """New entry in IPNS feed {feed}: {title}.
                 Click the message to open it""".format(
            feed=feedname,
            title=metadata['title'] if metadata['title'] else 'No title'
        )

        self.app.systemTrayMessage('IPNS', message, timeout=5000)

    def onIpfsInfos(self):
        dlg = IPFSInfosDialog(self.app)
        dlg.setWindowTitle(iIpfsInfos())
        self.app.task(dlg.loadInfos)
        dlg.exec_()

    def onConnReady(self):
        pass

    def onPubsubRx(self):
        now = QDateTime.currentDateTime()
        self.ui.pubsubStatusButton.setIcon(getIcon('network-transmit.png'))
        self.ui.pubsubStatusButton.setToolTip(
            'Pubsub: last message received {}'.format(now.toString()))

    def onPubsubTx(self):
        pass

    def showPinningStatusWidget(self):
        name = self.tabnPinning
        ft = self.findTabWithName(name)
        if ft:
            return self.ui.tabWidget.setCurrentWidget(ft)

        tab = self.pinStatusTab
        self.registerTab(tab, name, current=True,
                         icon=getIcon('pin-zoom.png'))

    def onPinItemsCount(self, count):
        statusMsg = iItemsInPinningQueue(count)

        if count > 0:
            self.ui.pinningStatusButton.setIcon(self.pinIconLoading)
        else:
            self.ui.pinningStatusButton.setIcon(self.pinIconNormal)

        self.ui.pinningStatusButton.setToolTip(statusMsg)
        self.ui.pinningStatusButton.setStatusTip(statusMsg)

    def onPinFinished(self, path):
        pass

    def onPinStatusChanged(self, qname, path, status):
        pass

    def onManualAvailable(self, lang, entry):
        self.menuManual.addAction(lang, functools.partial(
                                  self.onOpenManual, lang))

    def onOpenManual(self, lang):
        entry = self.app.manuals.getManualEntry(lang)
        if entry:
            self.addBrowserTab().browseIpfsHash(entry['Hash'])

    def enableButtons(self, flag=True):
        for btn in [
                self.clipboardManager,
                self.browseButton,
                self.fileManagerButton,
                self.chatRoomButton,
                self.peersButton,
                self.textEditorButton,
                self.mPlayerButton,
                self.profileEditButton]:
            btn.setEnabled(flag)

    def statusMessage(self, msg):
        self.ui.statusbar.showMessage(msg)

    def registerTab(self, tab, name, icon=None, current=False,
                    tooltip=None):
        idx = None
        if icon:
            idx = self.ui.tabWidget.addTab(tab, icon, name)
        else:
            idx = self.ui.tabWidget.addTab(tab, name)

        self._allTabs.append(tab)

        if current is True:
            self.ui.tabWidget.setCurrentWidget(tab)

        if tooltip and idx:
            self.ui.tabWidget.setTabToolTip(idx, tooltip)

    def findTabFileManager(self):
        return self.findTabWithName(self.tabnFManager)

    def findTabIndex(self, w):
        return self.ui.tabWidget.indexOf(w)

    def findTabWithName(self, name):
        for idx in range(0, self.ui.tabWidget.count()):
            tName = self.ui.tabWidget.tabText(idx)

            if tName == name:
                return self.ui.tabWidget.widget(idx)

    def removeTabFromWidget(self, w):
        idx = self.ui.tabWidget.indexOf(w)
        if idx:
            self.ui.tabWidget.removeTab(idx)

    def onSettings(self):
        runDialog(settings.SettingsDialog, self.app)

    def onCloseAllTabs(self):
        self.ui.tabWidget.clear()

    def onToggledPinAllGlobal(self, checked):
        self.pinAllGlobalChecked = checked

    def onAboutGalacteek(self):
        QMessageBox.about(self, 'About Galacteek', iAbout())

    @ipfsOp
    async def displayConnectionInfo(self, ipfsop):
        try:
            info = await ipfsop.client.core.id()
        except BaseException:
            return self.ui.ipfsStatusLabel.setText(iErrNoCx())

        nodeId = info.get('ID', iUnknown())
        nodeAgent = info.get('AgentVersion', iUnknownAgent())

        # Get IPFS peers list
        peers = await ipfsop.peersList()
        if not peers:
            return self.ui.ipfsStatusLabel.setText(
                iCxButNoPeers(nodeId, nodeAgent))

        message = iConnectStatus(nodeId, nodeAgent, len(peers))
        self.ui.ipfsStatusLabel.setText(message)

    def onMainTimerStatus(self):
        ensure(self.displayConnectionInfo())

    def keyPressEvent(self, event):
        # Ultimately this will be moved to configurable shortcuts

        modifiers = event.modifiers()

        if modifiers & Qt.ControlModifier:
            if event.key() == Qt.Key_T:
                self.addBrowserTab()
            if event.key() == Qt.Key_U:
                self.showPinningStatusWidget()
            if event.key() == Qt.Key_W:
                idx = self.ui.tabWidget.currentIndex()
                self.onTabCloseRequest(idx)

        super(MainWindow, self).keyPressEvent(event)

    def explore(self, multihash):
        ipfsPath = IPFSPath(multihash)
        if ipfsPath.valid:
            ensure(self.exploreIpfsPath(ipfsPath))
        else:
            messageBox(iInvalidInput())

    @ipfsOp
    async def exploreIpfsPath(self, ipfsop, ipfsPath):
        multihash = await ipfsPath.resolve(ipfsop)
        if not multihash:
            return messageBox(iCannotResolve(str(ipfsPath)))

        tabName = shortPathRepr(multihash)
        tooltip = 'Multihash explorer: {0}'.format(multihash)
        view = ipfsview.IPFSHashExplorerToolBox(self, multihash)
        self.registerTab(view, tabName, current=True,
                         icon=getIcon('hash.png'), tooltip=tooltip)

    def addMediaPlayerTab(self):
        name = self.tabnMediaPlayer
        ft = self.findTabWithName(name)
        if ft:
            return ft
        tab = mediaplayer.MediaPlayerTab(self)

        if tab.playerAvailable():
            self.registerTab(tab, name, icon=getIcon('multimedia.png'),
                             current=True)
            return tab
        else:
            messageBox(mediaplayer.iPlayerUnavailable())

    def mediaPlayerQueue(self, path, mediaName=None):
        tab = self.addMediaPlayerTab()
        if tab:
            tab.queueFromPath(path, mediaName=mediaName)

    def mediaPlayerPlay(self, path, mediaName=None):
        tab = self.addMediaPlayerTab()
        if tab:
            tab.playFromPath(path, mediaName=mediaName)

    def onTabCloseRequest(self, idx):
        tab = self.ui.tabWidget.widget(idx)

        if tab not in self.allTabs:
            return False

        if tab.onClose() is True:
            self.ui.tabWidget.removeTab(idx)
            self.allTabs.remove(tab)
            del tab

    def addEditorTab(self, path=None, editing=True):
        tab = TextEditorTab(editing=editing, parent=self)

        if isinstance(path, IPFSPath) and path.valid:
            tab.editor.display(path)

        self.registerTab(tab, iTextEditor(),
                         icon=getIcon('text-editor.png'), current=True)

    def addIpfsSearchView(self, text):
        if len(text) > 0:
            view = ipfssearch.IPFSSearchView(text, self)
            self.registerTab(view, iIpfsSearch(text), current=True,
                             icon=getIcon('search-engine.png'))

    def onOpenMediaPlayer(self):
        self.addMediaPlayerTab()

    def onOpenBrowserTabClicked(self, pinBrowsed=False):
        self.addBrowserTab(pinBrowsed=pinBrowsed)

    def onWriteNewDocumentClicked(self):
        w = textedit.AddDocumentWidget(self, parent=self.ui.tabWidget)
        self.registerTab(w, 'New document', current=True)

    def onPeersMgrClicked(self):
        self.showPeersMgr(current=True)

    def onFileManagerClicked(self):
        name = self.tabnFManager

        icon = getIcon('folder-open.png')
        ft = self.findTabWithName(name)
        if ft:
            ft.fileManager.updateTree()
            return self.ui.tabWidget.setCurrentWidget(ft)

        fileManagerTab = files.FileManagerTab(
            self.ui.tabWidget, fileManager=self.fileManagerWidget)
        self.registerTab(fileManagerTab, name, current=True, icon=icon)
        fileManagerTab.fileManager.updateTree()

    def onIpfsKeysClicked(self):
        name = self.tabnKeys
        ft = self.findTabWithName(name)
        if ft:
            return self.ui.tabWidget.setCurrentWidget(ft)

        keysTab = keys.KeysTab(self)
        self.registerTab(keysTab, name, current=True)

    def onHelpDonate(self):
        bcAddress = '3HSsNcwzkiWGu6wB18BC6D37JHExpxZvyS'
        runDialog(DonateDialog, bcAddress)

    def addBrowserTab(self, label='No page loaded', pinBrowsed=False,
                      current=True):
        icon = getIconIpfsIce()
        tab = browser.BrowserTab(self, pinBrowsed=pinBrowsed)
        self.registerTab(tab, label, icon=icon, current=current)

        if self.app.settingsMgr.isTrue(CFG_SECTION_BROWSER, CFG_KEY_GOTOHOME):
            tab.loadHomePage()

        return tab

    def addEventLogTab(self, current=False):
        self.registerTab(eventlog.EventLogWidget(self), iEventLog(),
                         current=current)

    def showPeersMgr(self, current=False):
        # Peers mgr
        name = iPeers()

        ft = self.findTabWithName(name)
        if ft:
            return self.ui.tabWidget.setCurrentWidget(ft)

        pMgr = peers.PeersManager(self, self.app.peersTracker)
        self.registerTab(pMgr, name, current=current)

    def quit(self):
        # Qt and application exit
        self.saveUiSettings()
        ensure(self.app.exitApp())

    def saveUiSettings(self):
        self.app.settingsMgr.setSetting(
            CFG_SECTION_UI,
            CFG_KEY_MAINWINDOW_GEOMETRY,
            self.saveGeometry())
        self.app.settingsMgr.setSetting(
            CFG_SECTION_UI,
            CFG_KEY_MAINWINDOW_STATE,
            self.saveState())

        self.app.settingsMgr.setSetting(
            CFG_SECTION_UI,
            CFG_KEY_BROWSER_AUTOPIN,
            self.pinAllGlobalButton.isChecked())

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.app.systemTrayMessage('Galacteek', iMinimized())

    def toggleIpfsSearchWidget(self, forceshow=False):
        btnPos = self.ipfsSearchButton.mapToGlobal(QPoint(0, 0))

        if self.toolbarMain.vertical:
            popupPoint = QPoint(btnPos.x() + 32, btnPos.y())
        elif self.toolbarMain.horizontal:
            popupPoint = QPoint(
                btnPos.x() - self.ipfsSearchWidget.width() - 30,
                btnPos.y() + 20)

        self.ipfsSearchWidget.move(popupPoint)

        if forceshow:
            self.ipfsSearchButton.setChecked(True)

        if self.ipfsSearchButton.isChecked() or forceshow:
            self.ipfsSearchButton.setIcon(self.ipfsSearchButton.iconActive)
            self.ipfsSearchWidget.show()
            self.ipfsSearchWidget.focus()
        else:
            self.ipfsSearchButton.setIcon(self.ipfsSearchButton.iconNormal)
            self.ipfsSearchWidget.hide()

    def addHashmarksTab(self):
        ft = self.findTabWithName(self.tabnHashmarks)
        if ft:
            return self.ui.tabWidget.setCurrentWidget(ft)

        if self.hashmarksPage is None:
            self.hashmarksPage = HashmarksPage(self.app.marksLocal,
                                               self.app.marksNetwork)

        tab = WebTab(self.ui.tabWidget)
        hview = DWebView(page=self.hashmarksPage)
        tab.attach(hview)

        self.registerTab(tab, iHashmarks(),
                         icon=getIcon('hashmarks.png'), current=True)

    def onOpenChatWidget(self):
        ft = self.findTabWithName(self.tabnChat)
        if ft:
            return self.ui.tabWidget.setCurrentWidget(ft)

        self.registerTab(self.chatRoomWidget, self.tabnChat,
                         icon=getIcon('chat.png'), current=True)
