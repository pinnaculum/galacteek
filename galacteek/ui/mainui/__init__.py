import functools

from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QToolBar
from PyQt5.QtWidgets import QMenu
from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QActionGroup
from PyQt5.QtWidgets import QToolButton
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QStackedWidget
from PyQt5.QtWidgets import QToolTip

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QUrl
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import QSize
from PyQt5.QtCore import QPoint
from PyQt5.QtCore import QRect
from PyQt5.QtCore import QEvent

from PyQt5.Qt import QSizePolicy

from PyQt5.QtGui import QKeySequence
from PyQt5.QtGui import QTextCursor

from PyQt5 import QtWebEngineWidgets

from galacteek import GALACTEEK_NAME
from galacteek import ensure
from galacteek import partialEnsure
from galacteek import log
from galacteek import database

from galacteek.appsettings import *

from galacteek.ai import openai as opai

from galacteek.core import runningApp
from galacteek.core.glogger import loggerMain
from galacteek.core.glogger import loggerUser
from galacteek.core.asynclib import asyncify
from galacteek.core.modelhelpers import *
from galacteek.core.ps import KeyListener
from galacteek.core.ps import makeKeyService
from galacteek.ipfs.wrappers import *
from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ui.chatbot import ChatBotSessionTab

from .logs import UserLogsWindow
from .logs import MainWindowLogHandler

from ..forms import ui_ipfsinfos

from .. import userwebsite
from .. import browser
from .. import files
from .. import keys
from .. import textedit
from .. import ipfssearch
from .. import eventlog
from ..files import unixfs

from ..dids import DIDExplorer
from ..clips import RotatingCubeClipSimple
from ..clips import RotatingCubeRedFlash140d
from ..textedit import TextEditorTab
from ..iprofile import ProfileEditDialog
from ..iprofile import ProfileButton
from ..pubsub import PubsubSnifferWidget
from ..pyramids import MultihashPyramidsToolBar
from ..quickaccess import QuickAccessToolBar
from ..daemonstats import BandwidthGraphView
from ..daemonstats import PeersCountGraphView
from ..camera import CameraController
from ..helpers import *
from ..pinning.pinstatus import RPSStatusButton
from ..pinning.pinstatus import PinStatusWidget
from ..widgets import AtomFeedsToolbarButton
from ..widgets import PopupToolButton
from ..widgets.hashmarks import HashmarkMgrButton
from ..widgets import AnimatedLabel
from ..widgets.netselector import IPFSNetworkSelectorToolButton
from ..widgets.toolbar import BasicToolBar

from ..widgets.torcontrol import TorControllerButton

from ..docks.appdock import *

from ..dialogs import *

from ..i18n import *

from ..dwebspace import *

from ..clipboard import ClipboardManager
from ..clipboard import ClipboardItemsStack


def iPinningItemStatus(pinPath, pinProgress):
    return QCoreApplication.translate(
        'GalacteekWindow',
        '\nPath: {0}, nodes processed: {1}').format(pinPath, pinProgress)


def iAboutGalacteek():
    from galacteek.__version__ import __version__
    from PyQt5.QtCore import QT_VERSION_STR

    return QCoreApplication.translate('GalacteekWindow', '''
        <p>
        <b>galacteek</b> is a multi-platform Qt5-based browser
        for the distributed web
        </p>
        <br/>

        <p>Website:
        <a href="https://galacteek.gitlab.io">
            https://galacteek.gitlab.io
        </a>
        </p>

        <p>GitLab:
        <a href="https://gitlab.com/galacteek/galacteek">
            https://gitlab.com/galacteek/galacteek
        </a>
        </p>
        <p>
        Author:
        <a href="mailto: BM-87dtCqLxqnpwzUyjzL8etxGK8MQQrhnxnt1@bitmessage">
        cipres (David Cipres)
        </a>
        </p>

        <p>galacteek version: {0}</p>
        <p>PyQt5 version: {1}</p>
        ''').format(__version__, QT_VERSION_STR)  # noqa


class IPFSDaemonStatusWidget(QWidget):
    def __init__(self, bwStatsView, peersStatsView, parent=None):
        super(IPFSDaemonStatusWidget, self).__init__(
            parent, Qt.Popup | Qt.FramelessWindowHint)

        self.app = QApplication.instance()
        self.ui = ui_ipfsinfos.Ui_IPFSInfosDialog()
        self.ui.setupUi(self)
        self.setWindowTitle(iIpfsInfos())

        self.labels = [self.ui.repoObjCount,
                       self.ui.repoVersion,
                       self.ui.repoSize,
                       self.ui.repoMaxStorage,
                       self.ui.nodeId,
                       self.ui.agentVersion,
                       self.ui.protocolVersion]

        self.ui.bwRateStatsLayout.addWidget(bwStatsView)
        self.ui.peersStatsLayout.addWidget(peersStatsView)

        self.setMinimumWidth(self.app.desktopGeometry.width() / 2)
        self.ui.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.ui.tabWidget.setStyleSheet(
            "QTabWidget::pane { background-color: lightgray; }")

    def enableLabels(self, enable):
        for label in self.labels:
            if not enable:
                label.setText('Fetching ...')

            label.setEnabled(enable)

    @ipfsOp
    async def update(self, ipfsop):
        self.enableLabels(False)
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


class WorkspacesToolBar(BasicToolBar):
    wsSwitched = pyqtSignal(BaseWorkspace)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.wsButtons = {}
        self.sepFirst = self.addSeparator()
        self.wsPlanetsToolBar = QToolBar()
        self.wsPlanetsToolBarAdded = False
        self.setAcceptDrops(True)

        self.setOrientation(Qt.Horizontal)
        self.setObjectName('workspacesToolBar')

        self.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding)

    def dragEnterEvent(self, ev):
        ev.accept()

    def add(self, btn, dst='default'):
        if dst == 'default':
            self.wsButtons[btn] = self.addWidget(btn)
        elif dst == 'planets':
            if not self.wsPlanetsToolBarAdded:
                # change that soon this is wrong
                self.addWidget(self.wsPlanetsToolBar)
                self.wsPlanetsToolBarAdded = True

            self.wsButtons[btn] = self.wsPlanetsToolBar.addWidget(btn)
        elif dst == 'qapps':
            self.wsButtons[btn] = self.insertWidget(self.sepFirst, btn)

    def buttonForWorkspace(self, workspace):
        for wsButton in self.wsButtons.keys():
            if wsButton.workspace is workspace:
                return wsButton

    def wsWasSwitched(self, workspace):
        # Current workspace has changed, update the buttons

        for wsButton in self.wsButtons.keys():
            if wsButton.workspace is workspace:
                wsButton.setChecked(True)
                wsButton.styleActive()
            else:
                # Repaint when unchecking an inactive workspace, in
                # rare cases it seems to still appear checked
                wsButton.setChecked(False)
                wsButton.repaint()

        self.wsSwitched.emit(workspace)


class CentralStack(QStackedWidget,
                   KeyListener):
    """
    Stacked widget holding the workspaces
    """

    def __init__(self,
                 wsToolBar: WorkspacesToolBar,
                 parent: QWidget = None):
        super().__init__(parent=parent)

        self.currentChanged.connect(partialEnsure(self.onWorkspaceChanged))
        self.toolBarWs = wsToolBar

        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)
        self.setContentsMargins(0, 0, 0, 0)
        self.setMouseTracking(True)

        self.psListen(makeKeyService('core', 'icapsuledb'))

        self.__wsDormant = []

    @property
    def mainWindow(self):
        return self.parent()

    @property
    def defaultWorkspace(self):
        idx, wspace = self.workspaceByName('@Earth')
        if wspace:
            return wspace

    def workspaces(self):
        for idx in range(0, self.count()):
            yield idx, self.workspaceFromIndex(idx)

        for ws in self.__wsDormant:
            yield -1, ws

    def workspacesBeforeIndex(self, widx):
        for idx in range(widx, self.count()):
            yield idx, self.workspaceFromIndex(idx)

    def workspaceFromIndex(self, idx):
        return self.widget(idx)

    def currentWorkspace(self):
        return self.currentIndex(), self.workspaceFromIndex(
            self.currentIndex())

    def previousWorkspace(self, w):
        idx = self.indexOf(w)

        if idx > 0:
            return idx - 1, self.widget(idx - 1)

        return -1, None

    def nextWorkspace(self, w):
        idx = self.indexOf(w)

        if idx < self.count():
            return idx + 1, self.widget(idx + 1)

        return -1, None

    def activateWorkspaces(self, flag=True):
        for idx, workspace in self.workspaces():
            workspace.setEnabled(flag)

    async def onWorkspaceChanged(self, idx):
        wspace = self.workspaceFromIndex(idx)
        if wspace:
            await wspace.workspaceSwitched()

        self.toolBarWs.wsWasSwitched(wspace)

    def __addWorkspace(self, workspace, position=-1):
        if not workspace.wsAttached:
            switchButton = workspace.createSwitchButton()

            if position >= 0:
                self.insertWidget(position, workspace)
            else:
                self.addWidget(workspace)

            workspace.wsAttached = True
            workspace.wsSwitchButton = switchButton

            if isinstance(workspace, TabbedWorkspace) or isinstance(
                    workspace, SingleWidgetWorkspace):
                self.toolBarWs.add(
                    switchButton,
                    dst=workspace.wsSection
                )

            workspace.setupWorkspace()

    def addWorkspace(self, workspace, section='default', dormant=False,
                     position=-1):
        workspace.wsSection = section

        if not dormant:
            self.__addWorkspace(workspace, position=position)

            workspace.wsSwitchButton.styleJustRegistered(True)
        else:
            self.__wsDormant.append(workspace)

    def addWorkspaces(self, *wspaces):
        [self.addWorkspace(w) for w in wspaces]

    def workspaceByName(self, name):
        for idx in range(self.count()):
            w = self.widget(idx)
            if w.wsName == name:
                return idx, w

        return None, None

    def workspaceCtx(self, name, show=True):
        idx, wspace = self.workspaceByName(name)
        if wspace:
            if show and self.currentWorkspace() is not wspace:
                wspace.wsSwitch()

            return wspace

    def createSwitchButton(self, wspace, pwspace, nwspace):
        return SwitchButton(pwspace, nwspace, self)

    def wsAddGlobalCustomAction(self, *args, **kw):
        for widx, ws in self.workspaces():
            ws.wsAddCustomAction(*args, **kw)

    def wsAddGlobalAction(self, action: QAction, default=False):
        for widx, ws in self.workspaces():
            ws.wsAddAction(action, default=default)

    def wsActivityNotify(self, workspace):
        widx, curWorkspace = self.currentWorkspace()
        wsButton = self.toolBarWs.buttonForWorkspace(workspace)

        if wsButton and curWorkspace is not workspace:
            wsButton.styleNotify()

    async def wsHashmarkTagRulesRun(self, hashmark):
        for idx, workspace in self.workspaces():
            match = await workspace.wsTagRulesMatchesHashmark(hashmark)

            if match and idx == -1:
                self.__addWorkspace(workspace)
                self.__wsDormant.remove(workspace)

                return workspace

        return None

    async def shutdown(self):
        for idx, w in self.workspaces():
            await w.workspaceShutDown()

    @ipfsOp
    async def event_g_services_core_icapsuledb(self, ipfsop, key, message):
        event = message['event']

        if event['type'] == 'QmlApplicationLoadRequest':
            icon = getIcon('galacteek.png')
            runSettings = event['runSettings']

            workspace = QMLDappWorkspace(
                self,
                event['appName'],
                event['appUri'],
                event['components'],
                event['depends'],
                event['qmlEntryPoint'],
                IPFSPath(event.get('appIconCid')),
                icon=icon,
                description=event['description']
            )

            if await workspace.load():
                self.addWorkspace(workspace, section='qapps')

                await runningApp().s.ldPublish({
                    'type': 'QmlApplicationLoaded',
                    'appUri': event['appUri']
                })

                await workspace.loadIcon()

                if runSettings['wsSwitch'] is True and 0:
                    workspace.wsSwitch()


class BrowseButton(PopupToolButton, KeyListener):
    """
    Browse button. When the button is hovered we play the
    rotating cube clip.
    """

    def __init__(self, parent=None):
        super().__init__(parent=parent, mode=QToolButton.InstantPopup)

        self.app = runningApp()
        self.animatedActions = []
        self.rotatingCubeClip = RotatingCubeClipSimple()
        self.rotatingCubeClip.finished.connect(
            functools.partial(self.rotatingCubeClip.start))
        self.rotatingCubeClip.frameChanged.connect(self.onCubeClipFrame)
        self.normalIcon()

    def setMenu(self, menu):
        super(BrowseButton, self).setMenu(menu)

        menu.triggered.connect(lambda action: self.normalIcon())
        menu.aboutToHide.connect(self.normalIcon)

    def onCubeClipFrame(self, no):
        icon = self.rotatingCubeClip.createIcon()

        self.setIcon(icon)

        if self.menu and self.menu.isVisible() and 0:
            for action in self.menu.actions():
                if action in self.animatedActions:
                    action.setIcon(icon)

    def rotateCube(self):
        if not self.rotatingCubeClip.playing():
            self.rotatingCubeClip.start()

    def normalIcon(self):
        self.rotatingCubeClip.stop()
        self.setIcon(getIconIpfs64())

    def enterEvent(self, event):
        self.rotateCube()
        super(BrowseButton, self).enterEvent(event)

    def leaveEvent(self, event):
        if not self.menu.isVisible() and self.isEnabled():
            self.normalIcon()

        super(BrowseButton, self).leaveEvent(event)


class MainWindow(QMainWindow, KeyListener):
    def __init__(self, app):
        super(MainWindow, self).__init__()

        self.setObjectName('gMainWindow')

        self.setWindowFlags(
            Qt.Window |
            Qt.CustomizeWindowHint |
            Qt.WindowTitleHint |
            Qt.WindowCloseButtonHint |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint
        )

        self._app = app
        self._allTabs = []
        self._lastFeedMark = None

        self.menuBar().hide()

        # Seems reasonable
        self.setMinimumSize(QSize(
            self.app.desktopGeometry.width() / 2,
            self.app.desktopGeometry.height() / 2)
        )

        # Prevent context menus on the main window (otherwise
        # the toolbars get the context menu on right click)
        self.setContextMenuPolicy(Qt.PreventContextMenu)

        # User logs widget
        self.logsPopupWindow = UserLogsWindow()
        self.logsPopupWindow.setObjectName('logsTextWindow')
        self.logsPopupWindow.setWindowTitle('{}: logs'.format(GALACTEEK_NAME))
        self.logsPopupWindow.hide()

        self.logsPopupWindow.setMinimumSize(QSize(
            (2 * self.app.desktopGeometry.width()) / 3,
            self.app.desktopGeometry.height() / 2
        ))

        self.userLogsHandler = MainWindowLogHandler(
            self.logsPopupWindow.logsBrowser, window=self,
            level='DEBUG' if self.app.debugEnabled else 'INFO')

        loggerMain.handlers.append(self.userLogsHandler)
        loggerUser.handlers.append(self.userLogsHandler)

        self.menuManual = QMenu(iManual(), self)

        # DID explorer
        self.didExplorer = DIDExplorer()

        # Global pin-all button
        self.pinAllGlobalButton = QToolButton(self)
        self.pinAllGlobalButton.setIcon(getIcon('pin.png'))
        self.pinAllGlobalButton.setObjectName('pinGlobalButton')
        self.pinAllGlobalButton.setToolTip(iGlobalAutoPinning())
        self.pinAllGlobalButton.setCheckable(True)
        self.pinAllGlobalButton.setAutoRaise(True)
        self.pinAllGlobalChecked = False
        self.pinAllGlobalButton.toggled.connect(self.onToggledPinAllGlobal)
        self.pinAllGlobalButton.setChecked(self.app.settingsMgr.browserAutoPin)

        # Toolbars
        self.toolbarWs = WorkspacesToolBar()

        # Apps/shortcuts toolbar
        self.toolbarQa = QuickAccessToolBar(self)
        self.toolbarPyramids = MultihashPyramidsToolBar()
        self.toolbarPyramids.setOrientation(self.toolbarQa.orientation())
        self.toolbarQa.attachPyramidsToolbar(self.toolbarPyramids)

        # Main actions and browse button setup
        self.quitAction = QAction(getIcon('quit.png'),
                                  iQuit(),
                                  shortcut=QKeySequence('Ctrl+q'),
                                  triggered=self.quit)
        self.quitAction.setShortcutVisibleInContextMenu(True)

        self.restartAction = QAction(getIcon('quit.png'),
                                     iRestart(),
                                     shortcut=QKeySequence('Alt+Shift+r'),
                                     triggered=self.app.restart)

        if self.app.windowsSystem:
            self.restartAction.setEnabled(False)

        self.mPlayerOpenAction = QAction(getIcon('mediaplayer.png'),
                                         iMediaPlayer(),
                                         triggered=self.onOpenMediaPlayer)

        self.psniffAction = QAction(getIcon('network-transmit.png'),
                                    iPubSubSniff(),
                                    self,
                                    triggered=self.openPsniffTab)

        self.editorOpenAction = QAction(getIcon('text-editor.png'),
                                        iTextEditor(),
                                        triggered=self.addEditorTab)

        self.editorOpenAction = QAction(getIcon('text-editor.png'),
                                        iTextEditor(),
                                        triggered=self.addEditorTab)

        self.browseAction = QAction(
            getIconIpfsIce(),
            iBrowse(),
            shortcut=QKeySequence('Ctrl+t'),
            triggered=self.onOpenBrowserTabClicked)
        self.browseAction.setShortcutVisibleInContextMenu(True)
        self.browseAutopinAction = QAction(
            getIconIpfsIce(),
            iBrowseAutoPin(),
            shortcut=QKeySequence('Ctrl+Alt+t'),
            triggered=functools.partial(self.onOpenBrowserTabClicked,
                                        pinBrowsed=True))
        self.browseAutopinAction.setShortcutVisibleInContextMenu(True)

        self.hashmarksCenterAction = QAction(
            getIcon('hashmarks-library.png'),
            iHashmarksDatabase(),
            shortcut=QKeySequence('Ctrl+h'),
            triggered=self.onOpenHashmarksCenter
        )

        self.chatBotSessionAction = QAction(
            getIcon('ai/chatbot.png'),
            iChatBotDiscussion(),
            shortcut=QKeySequence('Ctrl+Shift+c'),
            triggered=self.onNewChatBotSession
        )

        self.seedAppImageAction = QAction(
            getIcon('appimage.png'),
            'Seed AppImage',
            triggered=self.onSeedAppImage
        )

        # Pin status
        self.pinStatusWidget = PinStatusWidget(self, sticky=True)
        self.pinStatusWidget.hide()

        # File manager
        self.fileManagerWidget = files.FileManager(parent=self)

        # Camera controller
        self.cameraController = CameraController(parent=self)
        self.cameraController.setVisible(False)
        self.cameraController.cameraReady.connectTo(self.onCameraReady)

        # Edit-Profile button
        self.menuUserProfile = QMenu(self)
        self.profilesActionGroup = QActionGroup(self)

        # Profile button
        self.profileMenu = QMenu(self)
        iconProfile = getIcon('helmet.png')
        self.profileMenu.addAction(iconProfile,
                                   'Edit profile',
                                   self.onProfileEditDialog)
        self.profileMenu.addSeparator()

        self.userWebsiteManager = userwebsite.UserWebsiteManager(
            parent=self.profileMenu)

        self.profileButton = ProfileButton(
            menu=self.profileMenu,
            icon=iconProfile
        )
        self.profileButton.setEnabled(False)

        self.ll1 = QToolButton()
        self.ll1.setIcon(getIcon('hashmarks-library.png'))
        self.ll1.clicked.connect(self.onOpenHashmarksCenter)

        self.hashmarkMgrButton = HashmarkMgrButton(
            marks=self.app.marksLocal, parent=self)
        self.hashmarkMgrButton.setShortcut(
            QKeySequence('Super_L')
        )

        self.clipboardItemsStack = ClipboardItemsStack()

        # Clipboard loader button
        self.clipboardManager = ClipboardManager(
            self.app.clipTracker,
            self.clipboardItemsStack,
            self.app.resourceOpener,
            icon=getIcon('clipboard.png'),
            parent=self
        )

        # Atom
        self.atomButton = AtomFeedsToolbarButton()

        # Settings button
        settingsIcon = getIcon('settings.png')
        self.settingsToolButton = QToolButton()
        self.settingsToolButton.setIcon(settingsIcon)
        self.settingsToolButton.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self)
        menu.addAction(settingsIcon, iSettings(),
                       self.onSettings)
        menu.addSeparator()
        menu.addAction(settingsIcon, iConfigurationEditor(),
                       self.onRunConfigEditor)
        menu.addSeparator()

        if self.app.debugEnabled:
            menu.addAction(settingsIcon, iEventLog(),
                           self.onOpenEventLog)

        menu.addAction(getIcon('lock-and-key.png'), iKeys(),
                       self.onIpfsKeysClicked)
        menu.addSeparator()

        menu.addAction(self.psniffAction)
        menu.addSeparator()

        menu.addAction(iClearHistory(), self.onClearHistory)

        self.settingsToolButton.setMenu(menu)

        # Help button
        self.helpToolButton = QToolButton()
        self.helpToolButton.setObjectName('helpToolButton')
        self.helpToolButton.setIcon(getIcon('information.png'))
        self.helpToolButton.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self)
        menu.addMenu(self.menuManual)
        menu.addSeparator()

        dMenu = QMenu(iDonate(), self)
        dMenu.addAction(iDonateLiberaPay(), self.onHelpDonateLiberaPay)
        dMenu.addAction(iDonateKoFi(), self.onHelpDonateKoFi)
        dMenu.addAction(iDonateGithubSponsors(), self.onHelpDonateGSponsors)
        dMenu.addSeparator()
        dMenu.addAction(iDonateBitcoin(), self.onHelpDonateBitcoin)
        menu.addMenu(dMenu)

        menu.addAction('About', self.onAboutGalacteek)
        self.helpToolButton.setMenu(menu)

        # Quit button
        self.quitButton = PopupToolButton(mode=QToolButton.InstantPopup)
        self.quitButton.setObjectName('quitToolButton')
        self.quitButton.setIcon(self.quitAction.icon())
        self.quitButton.menu.addAction(self.restartAction)
        self.quitButton.menu.addSeparator()
        self.quitButton.menu.addAction(self.quitAction)
        self.quitButton.setToolTip(iQuit())

        self.ipfsSearchPageFactory = ipfssearch.SearchResultsPageFactory(self)

        self.hashmarkMgrButton.hashmarkClicked.connect(self.onHashmarkClicked)
        self.hashmarkMgrButton.searcher.hashmarkClicked.connect(
            self.onHashmarkClicked)

        # self.addToolBar(Qt.TopToolBarArea, self.toolbarMain)
        self.addToolBar(Qt.LeftToolBarArea, self.toolbarQa)

        self.stack = CentralStack(self.toolbarWs, parent=self)

        # Core workspace
        self.wspaceCore = WorkspaceCore(self.stack)

        self.wspaceStatus = WorkspaceStatus(self.stack, 'status')
        self.wspaceDapps = WorkspaceDapps(self.stack)
        self.wspacePeers = WorkspacePeers(self.stack)
        self.wspaceFs = WorkspaceFiles(self.stack)
        self.wspaceMessenger = WorkspaceMessenger(self.stack)
        self.wspaceMultimedia = WorkspaceMultimedia(self.stack)
        self.wspaceEdit = WorkspaceEdition(self.stack)
        self.wspaceManage = WorkspaceMisc(self.stack)

        self.webProfile = QtWebEngineWidgets.QWebEngineProfile.defaultProfile()

        # Status bar setup
        self.pinningStatusButton = QPushButton(self)
        self.pinningStatusButton.setObjectName('pinningStatusButton')
        self.pinningStatusButton.setShortcut(
            QKeySequence('Ctrl+u'))
        self.pinningStatusButton.setToolTip(iNoStatus())
        self.pinningStatusButton.setIcon(getIcon('pin-curve.png'))
        self.pinningStatusButton.clicked.connect(
            self.showPinningStatusWidget)
        # self.pubsubStatusButton = QPushButton(self)
        # self.pubsubStatusButton.setIcon(getIcon('network-offline.png'))

        self.rpsStatusButton = RPSStatusButton()
        self.rpsStatusButton.setIcon(getIcon('pin/pin-circle-red.png'))

        self.ipfsStatusCube = AnimatedLabel(
            RotatingCubeRedFlash140d(speed=10),
            parent=self
        )
        self.ipfsStatusCube.clip.setScaledSize(QSize(24, 24))
        self.ipfsStatusCube.hovered.connect(self.onIpfsInfosHovered)
        self.ipfsStatusCube.startClip()

        self.torControlButton = TorControllerButton(
            self.app.s.torService)
        self.torControlButton.setIcon(getIcon('tor.png'))
        self.torControlButton.setToolTip('Tor not connected yet')

        self.statusbar = self.statusBar()
        self.userLogsButton = QToolButton(self)
        self.userLogsButton.setToolTip('Logs')
        self.userLogsButton.setIcon(getIcon('logs.png'))
        self.userLogsButton.setCheckable(True)
        self.userLogsButton.toggled.connect(self.onShowUserLogs)
        self.logsPopupWindow.hidden.connect(
            functools.partial(self.userLogsButton.setChecked, False))

        self.networkSelectorButton = IPFSNetworkSelectorToolButton()
        self.networkSelectorButton.buildNetworksMenu()

        # Bandwidth graph
        self.bwGraphView = BandwidthGraphView(parent=None)
        self.peersGraphView = PeersCountGraphView(parent=None)
        self.ipfsDaemonStatusWidget = IPFSDaemonStatusWidget(
            self.bwGraphView, self.peersGraphView)

        self.lastLogLabel = QLabel(self.statusbar)
        self.lastLogLabel.setAlignment(Qt.AlignLeft)
        self.lastLogLabel.setObjectName('lastLogLabel')
        self.lastLogLabel.setTextFormat(Qt.RichText)

        self.lastLogTimer = QTimer()
        self.lastLogTimer.timeout.connect(self.onLastLogTimeout)

        self.statusbar.hide()

        # Connection status timer
        self.timerStatus = QTimer(self)
        self.timerStatus.timeout.connect(self.onMainTimerStatus)
        self.timerStatus.start(30000)

        self.enableButtons(False)

        # Docks

        self.appDock = DwebAppDock(
            self.toolbarWs,
            parent=self
        )

        self.appDock.addButton(self.hashmarkMgrButton)
        self.appDock.addButton(self.profileButton)
        self.appDock.addButton(self.cameraController)

        self.appDock.addToolWidget(self.clipboardItemsStack)
        self.appDock.addToolWidget(self.clipboardManager)
        self.appDock.addToolWidget(self.pinAllGlobalButton)

        self.appDock.addStatusWidget(self.ipfsStatusCube)
        self.appDock.addStatusWidget(self.networkSelectorButton)
        self.appDock.addStatusWidget(self.torControlButton)
        self.appDock.addStatusWidget(self.app.credsManager)

        self.appDock.addStatusWidget(self.pinningStatusButton)
        self.appDock.addStatusWidget(self.rpsStatusButton)
        self.appDock.addStatusWidget(self.settingsToolButton)
        self.appDock.addStatusWidget(self.userLogsButton)
        self.appDock.addStatusWidget(self.helpToolButton)
        self.appDock.addStatusWidget(self.quitButton)

        self.addDockWidget(Qt.BottomDockWidgetArea, self.appDock)

        # Connect the IPFS context signals
        self.app.ipfsCtx.ipfsConnectionReady.connectTo(self.onConnReady)
        self.app.ipfsCtx.ipfsRepositoryReady.connectTo(self.onRepoReady)

        self.app.ipfsCtx.profilesAvailable.connect(self.onProfilesList)
        self.app.ipfsCtx.profileChanged.connect(self.onProfileChanged)
        self.app.ipfsCtx.pinItemStatusChanged.connect(self.onPinStatusChanged)
        self.app.ipfsCtx.pinItemsCount.connect(self.onPinItemsCount)
        self.app.ipfsCtx.pinFinished.connect(self.onPinFinished)

        # Misc signals
        database.IPNSFeedMarkAdded.connectTo(self.onFeedMarkAdded)
        self.app.systemTray.messageClicked.connect(self.onSystrayMsgClicked)

        # Application signals
        self.app.manualAvailable.connect(self.onManualAvailable)

        previousGeo = self.app.settingsMgr.mainWindowGeometry
        if previousGeo:
            self.restoreGeometry(previousGeo)
        previousState = self.app.settingsMgr.mainWindowState
        if previousState:
            self.restoreState(previousState)

        self.hashmarksPage = None

        self.pinIconLoading = getIcon('pin-blue-loading.png')
        self.pinIconNormal = getIcon('pin-curve.png')

        self.setCentralWidget(self.stack)
        self.showMaximized()

        self.app.installEventFilter(self)

    @property
    def tabWidget(self):
        cur = self.stack.currentWidget()
        if cur:
            return cur.tabWidget

    @property
    def app(self):
        return self._app

    @property
    def allTabs(self):
        return self._allTabs

    def toolBarArea(self, toolbar):
        return Qt.AllToolBarArea

    def contextMessage(self, msgText: str):
        self.lastLogLabel.setText(msgText)
        self.lastLogTimer.start(4000)

    def onLastLogTimeout(self):
        self.lastLogLabel.setText('')
        self.lastLogTimer.stop()

    def eventFilter(self, obj, event):
        return False

    def eventFilterMouseMove(self, obj, event):
        # This wakes up auto-hiding toolbars (.widgets.SmartToolBar)
        # to be used when we use auto-hiding on one of the main toolbars

        if event.type() == QEvent.MouseMove and 0:
            if obj.objectName().startswith('gMainWindow'):
                if event.pos().y() < 5:
                    self.toolbarMain.wakeUp()
                else:
                    if self.toolbarMain.isVisible():
                        self.toolbarMain.unwanted()

        return False

    def changeEvent(self, event):
        if event.type() == QEvent.LanguageChange:
            log.debug(iLanguageChanged())

        super().changeEvent(event)

    def keyPressEvent(self, event):
        modifiers = event.modifiers()

        widx, curWorkspace = self.stack.currentWorkspace()

        if modifiers & Qt.ControlModifier:
            if event.key() == Qt.Key_W and curWorkspace:
                if isinstance(curWorkspace, TabbedWorkspace):
                    idx = curWorkspace.tabWidget.currentIndex()
                    ensure(curWorkspace.onTabCloseRequest(idx))

        super(MainWindow, self).keyPressEvent(event)

    def setupWorkspaces(self):
        self.stack.addWorkspace(self.wspaceStatus)

        self.stack.addWorkspace(self.wspaceCore)
        self.stack.addWorkspace(self.wspaceManage)
        self.stack.addWorkspace(self.wspaceFs)

        self.stack.addWorkspace(self.wspaceMultimedia)

        self.stack.addWorkspace(self.wspacePeers)
        self.stack.addWorkspace(self.wspaceEdit)
        self.stack.addWorkspace(self.wspaceMessenger)

        self.stack.addWorkspace(self.wspaceDapps)

        self.stack.wsAddGlobalAction(self.browseAction, default=True)
        self.stack.wsAddGlobalAction(self.hashmarksCenterAction, default=False)
        self.stack.wsAddGlobalAction(self.chatBotSessionAction, default=False)

        self.stack.activateWorkspaces(False)

    def onSeedAppImage(self):
        ensure(self.app.seedAppImage())

    def onClearHistory(self):
        self.app.urlHistory.clear()

    def onHashmarkClicked(self, hashmark):
        ensure(self.app.resourceOpener.openHashmark(hashmark))

    def onOpenEventLog(self):
        self.addEventLogTab(current=True)

    def onShowUserLogs(self, checked):
        lowerPos = self.mapToGlobal(QPoint(self.width(), self.height()))

        popupPoint = QPoint(
            lowerPos.x() - self.logsPopupWindow.width() - 64,
            lowerPos.y() - self.logsPopupWindow.height() - 64
        )

        self.logsPopupWindow.move(popupPoint)
        self.logsPopupWindow.logsBrowser.moveCursor(QTextCursor.End)
        self.logsPopupWindow.setVisible(checked)

    def onProfileEditDialog(self):
        runDialog(ProfileEditDialog, self.app.ipfsCtx.currentProfile,
                  title='IP profile')

    def onProfileWebsiteUpdated(self):
        self.profileButton.setStyleSheet('''
            QToolButton {
                background-color: #B7CDC2;
            }
        ''')
        self.app.loop.call_later(
            3, self.profileButton.setStyleSheet,
            'QToolButton {}'
        )

    @asyncify
    async def onProfileChanged(self, pName, profile):
        self.profileButton.setEnabled(False)

        if not profile.initialized:
            return

        await profile.userInfo.loaded
        self.profileButton.setEnabled(True)

        await self.profileButton.changeProfile(profile)

        for action in self.profilesActionGroup.actions():
            if action.data() == pName:
                action.setChecked(True)

                # Refresh the file manager
                fmTab = self.findTabFileManager()

                if fmTab:
                    fmTab.fileManager.setupModel()
                    fmTab.fileManager.pathSelectorDefault()

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

    async def onRepoReady(self):
        self.stack.activateWorkspaces(True)

        self.fileManagerWidget.setupModel()

        await self.app.ipfsCtx.peers.watchNetworkGraph()

        await self.displayConnectionInfo()
        await self.app.marksLocal.pyramidsInit()
        await self.app.sqliteDb.feeds.start()

        with self.stack.workspaceCtx(WS_FILES, show=False) as ws:
            await ws.importWelcome()

        with self.stack.workspaceCtx('@Earth', show=True) as ws:
            await ws.loadDapps()

        self.enableButtons()

    def onSystrayMsgClicked(self):
        # Open last shown mark in the systray
        if self._lastFeedMark is not None:
            self.addBrowserTab().browseFsPath(self._lastFeedMark.path)

    async def onFeedMarkAdded(self, feed, mark):
        self._lastFeedMark = mark

        message = """New entry in IPNS feed {feed}: {title}.
                 Click the message to open it""".format(
            feed=feed.name,
            title=mark.title if mark.title else 'No title'
        )

        self.app.systemTrayMessage('IPNS', message, timeout=10000)

    def onIpfsInfosHovered(self, hovered):
        if hovered is False:
            return

        statusCubePos = self.ipfsStatusCube.mapToGlobal(QPoint(0, 0))

        popupPoint = QPoint(
            statusCubePos.x() - self.ipfsDaemonStatusWidget.width() -
            self.ipfsStatusCube.width(),
            statusCubePos.y() - self.ipfsDaemonStatusWidget.height() -
            self.ipfsStatusCube.height()
        )

        self.ipfsDaemonStatusWidget.move(popupPoint)
        self.ipfsDaemonStatusWidget.setVisible(hovered)
        ensure(self.ipfsDaemonStatusWidget.update())

    async def onConnReady(self):
        pass

    def showPinningStatusWidget(self):
        pos = self.pinningStatusButton.mapToGlobal(QPoint(0, 0))

        popupPoint = QPoint(
            pos.x() - self.pinStatusWidget.width(),
            pos.y() - self.pinStatusWidget.height()
        )

        self.pinStatusWidget.move(popupPoint)
        self.pinStatusWidget.show()

    def onPinItemsCount(self, count):
        statusMsg = iItemsInPinningQueue(count)

        if count > 0:
            self.pinningStatusButton.setIcon(self.pinIconLoading)
            self.pinningStatusButton.setProperty('pinning', True)
        else:
            self.pinningStatusButton.setIcon(self.pinIconNormal)
            self.pinningStatusButton.setProperty('pinning', False)

        self.app.repolishWidget(self.pinningStatusButton)

        self.pinningStatusButton.setToolTip(statusMsg)
        self.pinningStatusButton.setStatusTip(statusMsg)

    def onPinFinished(self, path):
        pass

    def onPinStatusChanged(self, qname, path, status):
        pass

    def onManualAvailable(self, langCode, entry):
        lang = iLangEnglish() if langCode == 'en' else iUnknown()
        self.menuManual.addAction(lang, functools.partial(
                                  self.onOpenManual, langCode))

    def onOpenManual(self, lang):
        entry = self.app.manuals.getManualEntry(lang)
        if entry:
            self.addBrowserTab(workspace=WS_CONTROL).browseIpfsHash(
                entry['Hash']
            )

    def enableButtons(self, flag=True):
        for btn in [
                self.clipboardManager,
                # self.browseButton,
                self.cameraController,
                self.hashmarkMgrButton,
                self.toolbarWs,
                self.profileButton]:
            btn.setEnabled(flag)

    def statusMessage(self, msg, timeout=2500):
        self.userLogsButton.setToolTip(msg)

        if self.userLogsButton.isVisible():
            QToolTip.showText(
                self.userLogsButton.mapToGlobal(QPoint(0, 0)), msg,
                None, QRect(0, 0, 0, 0), timeout)

    def registerTab(self, tab, name, icon=None, current=True,
                    tooltip=None, workspace=None,
                    position='append',
                    wsSwitch=True):
        if workspace is None:
            sidx, wspace = self.stack.currentWorkspace()
        elif isinstance(workspace, str):
            sidx, wspace = self.stack.workspaceByName(workspace)
            if wspace is None:
                # XXX
                return
        elif issubclass(workspace.__class__, BaseWorkspace):
            wspace = workspace
        else:
            sidx, wspace = self.stack.currentWorkspace()

        if not wspace or not issubclass(wspace.__class__, TabbedWorkspace):
            # return
            wspace = self.stack.defaultWorkspace

        wspace.wsRegisterTab(tab, name, icon=icon, current=current,
                             tooltip=tooltip,
                             position=position)

        if self.stack.currentWorkspace() is not wspace and wsSwitch:
            wspace.wsSwitch()
        else:
            tab.tabActiveNotify()

    def findTabFileManager(self):
        with self.stack.workspaceCtx(WS_FILES, show=False) as ws:
            return ws.wsFindTabWithId('filemanager')

    def findTabIndex(self, w):
        return self.tabWidget.indexOf(w)

    def findTabWithName(self, name):
        for widx, workspace in self.stack.workspaces():
            tab = workspace.wsFindTabWithName(name)
            if tab:
                return workspace, tab

        return None, None

    def onSettings(self):
        with self.stack.workspaceCtx(WS_CONTROL) as wspace:
            wspace.showSettings()

    def onRunConfigEditor(self):
        with self.stack.workspaceCtx(WS_CONTROL) as wspace:
            wspace.openConfigEditor()

    def onToggledPinAllGlobal(self, checked):
        self.pinAllGlobalChecked = checked

    def onAboutGalacteek(self):
        runDialog(AboutDialog, iAboutGalacteek())

    def setConnectionInfoMessage(self, msg):
        self.app.systemTray.setToolTip('{app}: {msg}'.format(
            app=GALACTEEK_NAME, msg=msg))
        self.ipfsStatusCube.setToolTip(msg)

    @ipfsOp
    async def displayConnectionInfo(self, ipfsop):
        try:
            info = await ipfsop.client.core.id()
            assert info is not None

            bwStats = await ipfsop.client.stats.bw()

            # Get IPFS peers list
            peers = await ipfsop.peersList()
            assert peers is not None
            peersCount = len(peers)
        except Exception:
            self.setConnectionInfoMessage(iErrNoCx())
            return

        nodeId = info.get('ID', iUnknown())
        nodeAgent = info.get('AgentVersion', iUnknownAgent())

        if peersCount == 0:
            await ipfsop.noPeersFound()
            self.setConnectionInfoMessage(iCxButNoPeers(nodeId, nodeAgent))
            self.ipfsStatusCube.clip.setSpeed(0)
            return

        await ipfsop.peersCountStatus(peersCount)

        # Notify the bandwidth graph with the stats
        if isinstance(bwStats, dict):
            await self.bwGraphView.bwStatsFetched.emit(bwStats)

        await self.peersGraphView.peersCountFetched.emit(peersCount)

        # TODO: compute something more precise, probably based on the
        # swarm's high/low config
        connQuality = int((peersCount * 100) / 1000)

        self.setConnectionInfoMessage(
            iConnectStatus(nodeId, nodeAgent, peersCount))
        self.ipfsStatusCube.clip.setSpeed(5 + min(connQuality, 80))

    def stopTimers(self):
        self.timerStatus.stop()

    def onMainTimerStatus(self):
        ensure(self.displayConnectionInfo())

    def explore(self, cid):
        ipfsPath = IPFSPath(cid, autoCidConv=True)
        if ipfsPath.valid:
            ensure(self.exploreIpfsPath(ipfsPath))
        else:
            messageBox(iInvalidInput())

    @ipfsOp
    async def exploreIpfsPath(self, ipfsop, ipfsPath):
        cid = await ipfsPath.resolve(ipfsop)
        if not cid:
            return messageBox(iCannotResolve(str(ipfsPath)))

        path = IPFSPath(cid, autoCidConv=True)
        tabName = path.shortRepr()

        tooltip = 'CID explorer: {0}'.format(cid)
        view = unixfs.IPFSHashExplorerStack(self, cid)
        self.registerTab(view, tabName, current=True,
                         icon=getIcon('hash.png'), tooltip=tooltip)

    def getMediaPlayer(self):
        with self.stack.workspaceCtx(WS_MULTIMEDIA) as ws:
            return ws.mPlayerTab()

    def mediaPlayerQueue(self, path, playLast=False, mediaName=None):
        tab = self.getMediaPlayer()
        if tab:
            ensure(tab.queueFromPath(path, mediaName=mediaName,
                                     playLast=playLast))

    def mediaPlayerPlay(self, path, mediaName=None):
        tab = self.getMediaPlayer()
        if tab:
            ensure(tab.playFromPath(path, mediaName=mediaName))

    def onTabChanged(self, idx):
        tab = self.tabWidget.widget(idx)
        if tab:
            ensure(tab.onTabChanged())

    def openPsniffTab(self):
        self.registerTab(
            PubsubSnifferWidget(self), iPubSubSniff(), current=True,
            workspace=WS_CONTROL)

    def addEditorTab(self, path=None, editing=True):
        tab = TextEditorTab(editing=editing, parent=self)

        if isinstance(path, IPFSPath) and path.valid:
            tab.editor.display(path)

        self.registerTab(tab, iTextEditor(),
                         icon=getIcon('text-editor.png'), current=True,
                         tooltip=str(path),
                         workspace=WS_EDIT)

    def addIpfsSearchView(self):
        tab = ipfssearch.IPFSSearchTab(self)
        self.registerTab(tab, iIpfsSearch(), current=True,
                         icon=getIcon('search-engine.png'))
        tab.view.browser.setFocus(Qt.OtherFocusReason)

    async def onCameraReady(self, device: str):
        self.cameraController.setVisible(len(device) > 0)

    def onOpenMediaPlayer(self):
        self.getMediaPlayer()

    def onOpenBrowserTabClicked(self, pinBrowsed=False):
        sidx, wspace = self.stack.currentWorkspace()

        if not wspace or not issubclass(wspace.__class__, TabbedWorkspace):
            wspace = self.stack.defaultWorkspace

        self.addBrowserTab(pinBrowsed=pinBrowsed, urlFocus=True)

    def onWriteNewDocumentClicked(self):
        w = textedit.AddDocumentWidget(self, parent=self.tabWidget)
        self.registerTab(w, 'New document', current=True)

    def onIpfsKeysClicked(self):
        with self.stack.workspaceCtx(WS_CONTROL) as ws:
            tab = ws.wsFindTabWithId('ipfs-keys-manager')
            if tab:
                return ws.tabWidget.setCurrentWidget(tab)
            else:
                ws.wsRegisterTab(keys.KeysTab(self), iKeys(), current=True)

    def onHelpDonateGSponsors(self):
        self.addBrowserTab().enterUrl(
            QUrl('https://github.com/sponsors/pinnaculum')
        )

    def onHelpDonateLiberaPay(self):
        self.addBrowserTab().enterUrl(QUrl('https://liberapay.com/galacteek'))

    def onHelpDonateKoFi(self):
        self.addBrowserTab().enterUrl(QUrl('https://ko-fi.com/galacteek'))

    def onHelpDonateBitcoin(self):
        ensure(runDialogAsync(BTCDonateDialog))

    def onHelpDonatePatreon(self):
        tab = self.app.mainWindow.addBrowserTab(workspace='@Earth')
        tab.enterUrl(QUrl('https://patreon.com/galacteek'))

    def onOpenHashmarksCenter(self):
        # TODO: move to a method in TabbedWorkspace ?

        idx, ws = self.stack.currentWorkspace()

        if isinstance(ws, TabbedWorkspace):
            ws.openHashmarks(parent=self)

    def onNewChatBotSession(self):
        if opai.isConfigured():
            self.registerTab(ChatBotSessionTab(self),
                             iChatBotDiscussion(),
                             icon=getIcon('ai/chatbot.png'),
                             current=True)
        else:
            with self.stack.workspaceCtx(WS_CONTROL) as wspace:
                wspace.showSettings(showModule='ai')

    def addBrowserTab(self,
                      label='...',
                      pinBrowsed=False,
                      minProfile=None, current=True,
                      workspace=None,
                      wsSwitch=True,
                      urlFocus=False,
                      position='append'):
        icon = getIconIpfsIce()
        tab = browser.BrowserTab(self,
                                 minProfile=minProfile,
                                 pinBrowsed=pinBrowsed)
        self.registerTab(tab, label, icon=icon, current=current,
                         workspace=workspace,
                         wsSwitch=wsSwitch,
                         position=position)

        if urlFocus:
            tab.focusUrlZone()

        return tab

    def addEventLogTab(self, current=False):
        self.registerTab(eventlog.EventLogWidget(self), iEventLog(),
                         current=current,
                         workspace=WS_CONTROL)

    def quit(self):
        # Qt and application exit
        self.saveUiSettings()
        self.app.onExit()

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

    def getPyrDropButtonFor(self, ipfsPath, origin=None):
        return self.toolbarPyramids.getPyrDropButtonFor(
            ipfsPath, origin=origin)

    async def event_g_42(self, key, message):
        # Forward IPFS daemon events to the main ToolButton
        eType = message['event'].get('type')

        if eType == 'IpfsDaemonGoneEvent':
            # Daemon crash
            self.statusMessage(iIpfsDaemonCrashed(),
                               timeout=5000)

        if eType in ['IpfsDaemonStartedEvent',
                     'IpfsDaemonResumeEvent',
                     'IpfsDaemonGoneEvent',
                     'IpfsDaemonStoppedEvent']:
            await self.networkSelectorButton.processIpfsDaemonEvent(
                message['event']
            )
