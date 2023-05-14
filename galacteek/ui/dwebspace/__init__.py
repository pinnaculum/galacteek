import rule_engine
import weakref
import shutil
import traceback
from pathlib import Path

from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QTabWidget
from PyQt5.QtWidgets import QTabBar
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QToolBar
from PyQt5.QtWidgets import QToolButton
from PyQt5.QtWidgets import QToolTip
from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QSpacerItem
from PyQt5.QtWidgets import QStackedWidget

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QObject
from PyQt5.QtCore import QEvent
from PyQt5.QtCore import QSize
from PyQt5.QtCore import QPoint

from PyQt5.QtGui import QKeySequence
from PyQt5.QtGui import QIcon
from PyQt5.QtGui import QPixmap

from galacteek.ui.peers import PeersManager
from galacteek import partialEnsure
from galacteek import ensure
from galacteek import log
from galacteek import cached_property

from galacteek.ipfs import ipfsOp
from galacteek.ipfs.cidhelpers import IPFSPath

from galacteek.core import runningApp
from galacteek.core.tmpf import TmpFile

from galacteek.core.ps import KeyListener
from galacteek.core.ps import makeKeyService

from galacteek import services

from galacteek.ui.notify import uiNotify
from galacteek.ui import files
from galacteek.ui import ipfssearch
from galacteek.ui import textedit
from galacteek.ui import mediaplayer
from galacteek.ui import seeds


from galacteek.ui.helpers import getIcon
from galacteek.ui.helpers import getIconFromIpfs
from galacteek.ui.helpers import getPlanetIcon
from galacteek.ui.helpers import questionBoxAsync
from galacteek.ui.helpers import runDialogAsync
from galacteek.ui.notify import playSound

from galacteek.ui.dialogs import DefaultProgressDialog

from galacteek.ui.settings.cfgeditor import ConfigManager
from galacteek.ui.settings import SettingsCenterTab

from galacteek.ui.messenger import MessengerWidget

from galacteek.ui.userwebsite import WebsiteAddPostTab

from galacteek.ui.feeds import AtomFeedsViewTab
from galacteek.ui.qmlapp import QMLApplicationWidget

from galacteek.ui.icapsules import ICapsulesManagerWidget

from galacteek.ui.hashmarks.search import HashmarksCenterWidget

from galacteek.ui.widgets import URLDragAndDropProcessor
from galacteek.ui.i18n import *


class TabWidgetKeyFilter(QObject):
    nextPressed = pyqtSignal()
    closePressed = pyqtSignal()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            modifiers = event.modifiers()

            key = event.key()
            if modifiers & Qt.ControlModifier:
                if key == Qt.Key_J:
                    self.nextPressed.emit()
                    return True

                if key == Qt.Key_W:
                    self.closePressed.emit()
        return False


class WorkspaceSwitchButton(QToolButton, URLDragAndDropProcessor):
    def __init__(self, workspace, mode=QToolButton.InstantPopup,
                 parent=None, menu=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.workspace = workspace

        if mode == QToolButton.MenuButtonPopup and menu:
            self.setMenu(menu)

        self.setPopupMode(mode)
        self.setIcon(workspace.wsIcon)
        self.setObjectName('wsSwitchButton')
        self.setProperty("dropping", "false")
        self.setAcceptDrops(True)

        self.setToolTip(workspace.wsToolTip())

        self.ipfsObjectDropped.connect(self.onObjDropped)

    def flashToolTip(self):
        QToolTip.showText(
            self.mapToGlobal(QPoint(0, 0)),
            self.workspace.wsToolTip())

    def dragEnterEvent(self, event):
        if self.workspace.acceptsDrops:
            self.setProperty("dropping", "true")
            self.setStyle(QApplication.style())
            self.flashToolTip()
            event.accept()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setProperty("dropping", "false")
        self.setStyle(QApplication.style())
        super().dragLeaveEvent(event)

    def onObjDropped(self, path):
        ensure(self.workspace.handleObjectDrop(path))

    def checkStateSet(self):
        super(WorkspaceSwitchButton, self).checkStateSet()

    def nextCheckState(self):
        if self.workspace.stack.currentWorkspace() is not self.workspace:
            self.switch()
            self.setChecked(True)
        else:
            self.setChecked(False)

    def switch(self, soundNotify=False):
        self.workspace.wsSwitch(soundNotify=soundNotify)

    def styleJustRegistered(self, registered: bool):
        self.setProperty('wsJustRegistered', registered)
        runningApp().repolishWidget(self)

        if registered is True:
            runningApp().loop.call_later(
                5,
                self.styleJustRegistered,
                not registered
            )

    def styleNotify(self):
        self.setProperty('wsNotify', True)
        self.setStyleSheet('''
            QToolButton {
                background-color: #B7CDC2;
            }
        ''')

    def styleActive(self):
        self.setProperty('wsActive', True)
        self.setStyleSheet('''
            QToolButton::hover {
                background-color: #4a9ea1;
            }

            QToolBar QToolButton::pressed {
                background-color: #eec146;
            }
        ''')


class MainTabBar(QTabBar):
    def __init__(self, parent):
        super().__init__(parent=parent)
        self.setAcceptDrops(True)
        self.setObjectName('wsTabBar')
        self.tabWidget = parent
        self.setIconSize(QSize(24, 24))

    def dragEnterEvent(self, event):
        event.accept()

    def dropEvent(self, event):
        tabIdx = self.tabAt(event.pos())
        tab = self.tabWidget.widget(tabIdx)

        if tab:
            self.tabWidget.tabDropProcessEvent(tab, event)


class MainTabWidget(QTabWidget):
    onTabInserted = pyqtSignal(int)
    onTabRemoved = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.setTabBar(MainTabBar(self))
        self.setTabsClosable(True)
        self.setElideMode(Qt.ElideMiddle)
        self.setUsesScrollButtons(True)
        self.setObjectName('wsTabWidget')
        self.setAcceptDrops(True)
        self.setContentsMargins(0, 0, 0, 0)

        tabKeyFilter = TabWidgetKeyFilter(self)
        tabKeyFilter.nextPressed.connect(self.cycleTabs)
        tabKeyFilter.closePressed.connect(self.closeCurrentTab)

    def tabDropProcessEvent(self, tab, event):
        tab.tabDropEvent(event)

    def removeTabFromWidget(self, w):
        idx = self.tabWidget.indexOf(w)
        if idx:
            self.tabWidget.removeTab(idx)

    def closeCurrentTab(self):
        self.tabCloseRequested.emit(self.currentIndex())

    def cycleTabs(self):
        curIndex = self.currentIndex()
        if curIndex + 1 < self.count():
            self.setCurrentIndex(curIndex + 1)
        else:
            self.setCurrentIndex(0)

    def tabInserted(self, index):
        self.onTabInserted.emit(index)
        super().tabInserted(index)

    def tabRemoved(self, index):
        self.onTabRemoved.emit(index)
        super().tabRemoved(index)


class ToolBarActionsContainer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        hLayout = QHBoxLayout(self)
        self.setLayout(hLayout)

        self.toolBar = QToolBar()
        self.toolBar.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        hLayout.addItem(
            QSpacerItem(40, 0, QSizePolicy.Expanding, QSizePolicy.Maximum))
        hLayout.addWidget(self.toolBar)


WS_STATUS = 'status'
WS_MAIN = 'main'
WS_PEERS = 'peers'
WS_FILES = 'files'
WS_MULTIMEDIA = 'multimedia'
WS_EDIT = 'edit'
WS_SEARCH = 'search'
WS_CONTROL = 'control'
WS_DMESSENGER = 'dmessenger'


class BaseWorkspace(QWidget):
    listenTo = []

    def __init__(self, stack,
                 name,
                 description=None,
                 section='default',
                 icon=None,
                 acceptsDrops=False):
        super().__init__(parent=stack)

        self.app = QApplication.instance()
        self.acceptsDrops = acceptsDrops

        self.stack = stack
        self.wsName = name
        self.wsDescription = description
        self.wsSection = section
        self.wsAttached = False
        self.wsSwitchButton = None
        self.wsIcon = icon if icon else getIcon('galacteek.png')
        self.defaultAction = None
        self.wLayout = QVBoxLayout(self)
        self.setLayout(self.wLayout)

        self.wLayout.setSpacing(0)
        self.wLayout.setContentsMargins(0, 0, 0, 0)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def changeIcon(self, icon: QIcon):
        # Change workspace icon
        self.wsIcon = icon

        if self.wsSwitchButton:
            self.wsSwitchButton.setIcon(self.wsIcon)

    def setupWorkspace(self):
        pass

    def createSwitchButton(self, parent=None):
        return WorkspaceSwitchButton(self, parent=parent)

    async def workspaceShutDown(self):
        pass

    async def loadDapps(self):
        pass

    async def handleObjectDrop(self, ipfsPath):
        pass

    def wsToolTip(self):
        return self.wsDescription

    def empty(self):
        return True

    def workspaceIdx(self):
        return self.stack.indexOf(self)

    def previousWorkspace(self):
        return self.stack.previousWorkspace(self)

    def nextWorkspace(self):
        return self.stack.nextWorkspace(self)

    async def workspaceSwitched(self):
        await self.triggerDefaultActionIfEmpty()

    async def triggerDefaultActionIfEmpty(self):
        if self.empty() and self.defaultAction:
            self.defaultAction.trigger()

    def wsAddCustomAction(self, actionName: str, icon, name,
                          func, default=False):
        pass

    def wsAddAction(self, action: QAction, default=False):
        pass

    def wsAddWidget(self, widget):
        pass

    async def onTabCloseRequest(self, idx):
        pass

    def wsSwitch(self, soundNotify=False):
        self.stack.setCurrentIndex(self.workspaceIdx())

    async def wsTagRulesMatchesHashmark(self, hashmark):
        return False


class SingleWidgetWorkspace(BaseWorkspace):
    def setupWorkspace(self):
        pass


class DefaultStatusWidget(QWidget):
    pass


class WorkspaceStatus(BaseWorkspace):
    def setupWorkspace(self):
        self.pile = QStackedWidget(self)
        self.wLayout.addWidget(self.pile)
        self.dlgs = weakref.WeakValueDictionary()

        self.pile.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.push(DefaultStatusWidget(), 'default')

    def push(self, widget, name):
        idx = self.pile.addWidget(widget)
        self.pile.setCurrentIndex(idx)
        self.dlgs[name] = widget
        return idx, widget

    def clear(self, name):
        if name in self.dlgs:
            w = self.dlgs[name]
            idx = self.pile.indexOf(w)
            if idx:
                self.pile.removeWidget(w)

    def pushProgress(self, name):
        return self.push(DefaultProgressDialog(), name)

    async def pushRunDialog(self, dialog, name):
        dialog.setEnabled(True)
        idx, w = self.push(dialog, name)
        await runDialogAsync(dialog)


class WsDappsSwitchButton(WorkspaceSwitchButton):
    def switch(self, soundNotify=False):
        self.workspace.refreshDapps()

        self.workspace.wsSwitch(soundNotify=soundNotify)


class WorkspaceDapps(SingleWidgetWorkspace):
    def __init__(self, stack):
        super().__init__(stack, 'dapps',
                         icon=getIcon('capsules/icapsule-green.png'),
                         description='Dapps')

    def setupWorkspace(self):
        super().setupWorkspace()

        self.dappsManager = ICapsulesManagerWidget(parent=self)
        self.wLayout.addWidget(self.dappsManager)

    def refreshDapps(self):
        self.dappsManager.refresh()

    def createSwitchButton(self, parent=None):
        return WsDappsSwitchButton(self, parent=parent)


class LinkedDataWsMixin:
    def openHashmarks(self, parent=None):
        hashmarksLdCenter = HashmarksCenterWidget(parent)

        self.wsRegisterTab(
            hashmarksLdCenter,
            iHashmarks(),
            current=True,
            icon=getIcon('hashmarks-library.png')
        )

        hashmarksLdCenter.refresh()


class TabActionsToolBar(QToolBar):
    pass


class TabbedWorkspace(LinkedDataWsMixin,
                      BaseWorkspace):
    def __init__(self, stack,
                 name,
                 description=None,
                 section='default',
                 icon=None,
                 acceptsDrops=False,
                 inactiveTabsNotify=False):
        super(TabbedWorkspace, self).__init__(
            stack, name, description=description,
            section=section, icon=icon,
            acceptsDrops=acceptsDrops
        )

        self.wsTagRules = []
        self.wsActions = {}

        self.previousOpenedTabIdx = -1
        self.inactiveTabsNotify = inactiveTabsNotify

        self.toolBarWsActions = QToolBar(self)
        self.toolBarWsActions.setObjectName('wsActionsToolBar')
        self.toolBarTabActions = TabActionsToolBar(self)
        self.toolBarTabActions.setObjectName('tabActionsToolBar')

    def wsToolTip(self):
        return self.wsDescription

    def wsTabs(self):
        for tidx in range(self.tabWidget.count()):
            yield tidx, self.tabWidget.widget(tidx)

    def wsFindTabWithName(self, name):
        for idx in range(0, self.tabWidget.count()):
            tName = self.tabWidget.tabText(idx)

            if tName.strip() == name.strip():
                return self.tabWidget.widget(idx)

    def wsFindTabWithId(self, id):
        for tidx, tab in self.wsTabs():
            if tab and tab.ctx.tabIdent == id:
                return tab

    def empty(self):
        return self.tabWidget.count() == 0

    def workspaceIdx(self):
        return self.stack.indexOf(self)

    def setupWorkspace(self):
        # Workspace's tab widget and toolbars
        self.tabWidget = MainTabWidget(self)

        self.wLayout.addWidget(self.tabWidget)

        self.tabWidget.setElideMode(Qt.ElideMiddle)
        self.tabWidget.setUsesScrollButtons(True)
        self.tabWidget.onTabRemoved.connect(
            partialEnsure(self.wsTabRemoved))
        self.tabWidget.currentChanged.connect(
            partialEnsure(self.wsTabChanged))
        self.tabWidget.tabCloseRequested.connect(
            partialEnsure(self.onTabCloseRequest))
        self.tabWidget.tabBarDoubleClicked.connect(
            partialEnsure(self.onTabDoubleClicked))

        if self.app.system != 'Darwin':
            self.tabWidget.setDocumentMode(True)

        # Set the corner widgets
        # Tab actions on the left, ws actiions on the riight

        self.setCornerLeft(self.toolBarTabActions)
        self.setCornerRight(self.toolBarWsActions)

        # Pinned actions

        self.actionPostBlog = self.wsAddCustomAction(
            'blogpost', getIcon('feather-pen.png'),
            iNewBlogPost(), self.onAddBlogPost
        )

    def onAddBlogPost(self):
        self.wsRegisterTab(
            WebsiteAddPostTab(self.app.mainWindow),
            iNewBlogPost(),
            current=True,
            icon=self.actionPostBlog.icon()
        )

    async def workspaceShutDown(self):
        for tabIdx, tab in self.wsTabs():
            await tab.onClose()

    def setCornerLeft(self, widget: QWidget):
        self.tabWidget.setCornerWidget(widget, Qt.TopLeftCorner)

    def setCornerRight(self, widget: QWidget):
        self.tabWidget.setCornerWidget(widget, Qt.TopRightCorner)

    def previousWorkspace(self):
        return self.stack.previousWorkspace(self)

    def nextWorkspace(self):
        return self.stack.nextWorkspace(self)

    def wsRegisterTab(self, tab, name, icon=None, current=False,
                      tooltip=None,
                      position='append'):
        curIdx = self.tabWidget.currentIndex()
        if curIdx >= 0:
            self.previousOpenedTabIdx = curIdx

        if position == 'append':
            atIdx = self.tabWidget.count()
        elif position == 'nextcurrent':
            atIdx = curIdx + 1

        if icon:
            idx = self.tabWidget.insertTab(atIdx, tab, icon, name)
        else:
            idx = self.tabWidget.insertTab(atIdx, tab, name)

        tab.workspaceAttach(self)

        if current is True:
            self.tabWidget.setCurrentWidget(tab)
            tab.setFocus(Qt.OtherFocusReason)

        if tooltip and idx:
            self.tabWidget.setTabToolTip(idx, tooltip)

    async def workspaceSwitched(self):
        uiNotify(f'workspaceSwitched.{self.wsName}')

        await self.triggerDefaultActionIfEmpty()

    async def wsTabChanged(self, tabidx):
        tab = self.tabWidget.widget(tabidx)
        if tab:
            await tab.onTabChanged()

        if self.inactiveTabsNotify:
            # notify other tabs that they aren't active now

            for idx in range(self.tabWidget.count()):
                if idx == tabidx:
                    continue
                itab = self.tabWidget.widget(idx)
                if itab:
                    await itab.onTabHidden()

        #
        # Register the tab actions in the tab actions toolbar
        #
        # First we disable updates on the tab bar to avoid flickering
        #

        tbar = self.tabWidget.tabBar()
        tbar.setUpdatesEnabled(False)

        self.toolBarTabActions.clear()

        for widgetAction in tab.tabActions():
            self.toolBarTabActions.addAction(widgetAction)

        # Re-enable updates on the tab bar
        tbar.setUpdatesEnabled(True)

        # Trick or treat
        self.app.loop.call_later(
            0.1,
            QCoreApplication.sendEvent,
            tbar,
            QEvent(QEvent.FontChange)
        )

    async def wsTabRemoved(self, tabidx):
        await self.triggerDefaultActionIfEmpty()

    async def triggerDefaultActionIfEmpty(self):
        if self.empty() and self.defaultAction:
            self.defaultAction.trigger()

    def wsAddCustomAction(self, actionName: str, icon, name,
                          func, default=False,
                          shortcut=None):
        action = self.toolBarWsActions.addAction(
            icon, name, func
        )
        self.wsActions[actionName] = action

        if shortcut:
            action.setShortcut(shortcut)

        if default is True and not self.defaultAction:
            self.defaultAction = action

        return action

    def wsAddAction(self, action: QAction, default=False):
        self.toolBarWsActions.addAction(action)

        if default is True and not self.defaultAction:
            self.defaultAction = action

        if len(list(self.toolBarWsActions.actions())) == 1 and \
                not self.defaultAction:
            # Only one action yet, make it the default
            self.defaultAction = action

    def wsAddWidget(self, widget):
        self.toolBarWsActions.addWidget(widget)

    async def onTabDoubleClicked(self, idx):
        tab = self.tabWidget.widget(idx)
        if tab:
            await tab.onTabDoubleClicked()

    async def onTabCloseRequest(self, idx):
        tab = self.tabWidget.widget(idx)

        if tab is None:
            # TODO
            return

        if tab.sticky is True:
            # Sticky tab
            return

        if await tab.onClose() is True:
            self.tabWidget.removeTab(idx)
            tab.deleteLater()

            if self.previousOpenedTabIdx >= 0:
                self.tabWidget.setCurrentIndex(self.previousOpenedTabIdx)

    def wsSwitch(self, soundNotify=False):
        self.stack.setCurrentIndex(self.workspaceIdx())

        if soundNotify and 0:
            playSound('wsswitch.wav')

    async def wsTagRulesMatchesHashmark(self, hashmark):
        from galacteek.ld.rdf.hashmarks import tagsForHashmark

        result = await tagsForHashmark(hashmark['uri'])
        tags = [
            {
                'tag': str(r['tagName'])
            } for r in result
        ]

        for rule in self.wsTagRules:
            res = list(rule.filter(tags))
            if len(res) > 0:
                return True

        return False


class WorkspaceCore(TabbedWorkspace):
    def __init__(self, stack):
        super().__init__(stack,
                         '@Earth',
                         icon=getIcon('planets/globe-grid.png'))

        self.wsTagRules.append(rule_engine.Rule('tag =~ ".*"'))

    def wsToolTip(self):
        return 'Main workspace'

    def onHelpBrowsing(self):
        self.app.manuals.browseManualPage('browsing.html')

    async def loadDapps(self):
        pass

    def setupWorkspace(self):
        super().setupWorkspace()

        self.wsAddCustomAction(
            'help-browsing', getIcon('help.png'),
            iHelp(), self.onHelpBrowsing)

        action = self.wsAddCustomAction('search',
                                        getIcon('search-engine.png'),
                                        iIpfsSearch(),
                                        self.onAddSearchTab,
                                        default=False)
        action.setShortcut(QKeySequence('Ctrl+s'))

    def onAddSearchTab(self):
        tab = ipfssearch.IPFSSearchTab(self.app.mainWindow)
        self.wsRegisterTab(tab, iIpfsSearch(), current=True,
                           icon=getIcon('search-engine.png'))
        tab.view.browser.setFocus(Qt.OtherFocusReason)


class PlanetWorkspace(TabbedWorkspace):
    def __init__(self, stack,
                 planetName,
                 description=None,
                 icon=None):
        super().__init__(
            stack,
            f'@{planetName}',
            description=description,
            icon=getPlanetIcon(planetName.lower())
        )

        self._planet = planetName

        self.wsTagRules.append(rule_engine.Rule(
            f'tag =~ "@{planetName}#.*"'
        ))

    @property
    def planet(self):
        return self._planet

    def wsToolTip(self):
        return f'Planet workspace: {self.planet}'

    def onHelpBrowsing(self):
        self.app.manuals.browseManualPage('browsing.html')

    async def loadDapps(self):
        self.app = QApplication.instance()

        await self.app.dappsRegistry.loadDapp('multihash_palace')

        if self.app.cmdArgs.enablequest and 0:
            await self.loadQuestService()

    async def loadQuestService(self):
        from galacteek.dweb.quest import loadQuestService
        self.qView, self.qPage = await loadQuestService()

    def setupWorkspace(self):
        super().setupWorkspace()
        self.wsAddCustomAction(
            'help-browsing', getIcon('help.png'),
            iHelp(), self.onHelpBrowsing)


class WorkspaceFiles(TabbedWorkspace):
    def __init__(self, stack):
        super().__init__(stack, WS_FILES,
                         icon=getIcon('folder-open-orange.png'),
                         description='Files')

        self.btClient = None

    def setupWorkspace(self):
        super().setupWorkspace()

        fileManager = self.app.mainWindow.fileManagerWidget

        self.fileManagerTab = files.FileManagerTab(
            self.app.mainWindow,
            fileManager=fileManager
        )

        icon = getIcon('folder-open.png')

        self.wsRegisterTab(self.fileManagerTab, iFileManager(), icon)
        if 0:
            self.seedsTab = seeds.SeedsTrackerTab(self.app.mainWindow)
            self.wsRegisterTab(self.seedsTab, iFileSharing(),
                               getIcon('fileshare.png'))

        self.wsAddAction(fileManager.addFilesAction)
        self.wsAddAction(fileManager.addDirectoryAction)
        # self.wsAddAction(fileManager.newSeedAction)

        self.actionTorrentClient = self.wsAddCustomAction(
            iBitTorrentClient(), getIcon('torrent.png'),
            iBitTorrentClient(),
            partialEnsure(self.onStartTorrentClient)
        )

        self.actionGc = self.wsAddCustomAction(
            'gc', getIcon('clear-all.png'),
            iGarbageCollectRun(),
            partialEnsure(self.onRunGC)
        )

    async def workspaceShutDown(self):
        try:
            btClient = self.btClient()
            assert btClient is not None
        except Exception:
            pass
        else:
            await btClient.stop()

    async def getTorrentClient(self, show=True):
        try:
            from galacteek.ui.torrentgui import TorrentClientTab
        except ImportError:
            # bt client should be a service now
            return None

        try:
            btClient = self.btClient()
            assert btClient is not None
        except Exception:
            btClient = TorrentClientTab(self.app.mainWindow)
            await btClient.start()
            self.btClient = weakref.ref(btClient)

        ex = self.wsFindTabWithId('btclient')
        if not ex:
            self.wsRegisterTab(
                btClient, iBitTorrentClient(), getIcon('torrent.png'))

        if show:
            self.tabWidget.setCurrentWidget(btClient)

        return btClient

    async def onStartTorrentClient(self, *a):
        await self.getTorrentClient(show=True)

    async def seedsSetup(self):
        # await self.seedsTab.loadSeeds()
        pass

    async def importWelcome(self):
        pass

    async def onRunGC(self):
        tab = self.wsFindTabWithId('gcrunner')

        if not tab and await questionBoxAsync(iGarbageCollector(),
                                              iGarbageCollectRunAsk()):

            gcRunnerTab = files.GCRunnerTab(self.app.mainWindow)
            gcRunnerTab.gcClosed.connectTo(self.onGcFinished)

            self.wsRegisterTab(gcRunnerTab, iGarbageCollector(),
                               self.actionGc.icon(), current=True)
            self.actionGc.setEnabled(False)
            ensure(gcRunnerTab.run())

    async def onGcFinished(self):
        self.actionGc.setEnabled(True)

    async def workspaceSwitched(self):
        await super().workspaceSwitched()

        self.fileManagerTab.fileManager.updateTree()


class WorkspaceMultimedia(SingleWidgetWorkspace):
    def __init__(self, stack):
        super().__init__(stack, WS_MULTIMEDIA,
                         icon=getIcon('multimedia/mplayer1.png'),
                         description='Mediaplayer',
                         acceptsDrops=True)

    @cached_property
    def mPlayer(self):
        return mediaplayer.MediaPlayerTab(self.app.mainWindow)

    def setupWorkspace(self):
        super().setupWorkspace()

        self.wLayout.addWidget(self.mPlayer)

    def mPlayerTab(self):
        return self.mPlayer

    async def workspaceSwitched(self):
        self.mPlayer.update()

    async def handleObjectDrop(self, ipfsPath):
        tab = self.mPlayerTab()
        if tab:
            await tab.queueFromPath(ipfsPath.objPath)


class WorkspaceSearch(TabbedWorkspace):
    def __init__(self, stack):
        super().__init__(stack, WS_SEARCH, icon=getIcon('search-engine.png'),
                         description='Search')

    def setupWorkspace(self):
        super().setupWorkspace()

        action = self.wsAddCustomAction('search', self.wsIcon, iIpfsSearch(),
                                        self.onAddSearchTab, default=True)
        action.setShortcut(QKeySequence('Ctrl+s'))

        if 0:
            self.hCenterAction = self.wsAddCustomAction(
                'hashmarkscenter',
                getIcon('hashmarks-library.png'),
                iHashmarksDatabase(),
                self.onOpenHashmarksCenter
            )

    def onOpenHashmarksCenter(self):
        hashmarksLdCenter = HashmarksCenterWidget(
            self.app.mainWindow)

        self.wsRegisterTab(
            hashmarksLdCenter,
            iHashmarksDatabase(),
            current=True,
            icon=getIcon('hashmarks-library.png')
        )

        hashmarksLdCenter.refresh()

        self.wsSwitch()

    def onAddSearchTab(self):
        tab = ipfssearch.IPFSSearchTab(self.app.mainWindow)
        self.wsRegisterTab(tab, iIpfsSearch(), current=True,
                           icon=self.wsIcon)
        tab.view.browser.setFocus(Qt.OtherFocusReason)


class WorkspaceEdition(TabbedWorkspace):
    def __init__(self, stack):
        super().__init__(stack, WS_EDIT, icon=getIcon('feather-pen.png'),
                         description='Edition')

    def setupWorkspace(self):
        super().setupWorkspace()

        self.actionTextEdit = self.wsAddCustomAction(
            'textedit', getIcon('text-editor.png'),
            iTextEditor(), self.onAddTextEditorTab, default=True)

        self.actionHelp = self.wsAddCustomAction(
            'help', getIcon('help.png'),
            iHelp(), self.onHelpEditing)

        self.actionMarkdownHelp = self.wsAddCustomAction(
            'help', getIcon('markdown.png'),
            'Have you completely lost your Markdown ?',
            self.onHelpMarkdown)

        self.actionPostBlog = self.wsAddCustomAction(
            'blogpost', getIcon('feather-pen.png'),
            iNewBlogPost(), self.onAddBlogPost)

    def onHelpEditing(self):
        self.app.manuals.browseManualPage('editing.html')

    def onHelpMarkdown(self):
        self.app.manuals.browseManualPage('markdown.html')

    def onAddTextEditorTab(self):
        tab = textedit.TextEditorTab(editing=True, parent=self)
        self.wsRegisterTab(
            tab, iTextEditor(), current=True,
            icon=self.actionTextEdit.icon())

    def onAddBlogPost(self):
        from galacteek.ui.userwebsite import WebsiteAddPostTab

        tab = WebsiteAddPostTab(self.app.mainWindow)
        self.wsRegisterTab(
            tab, iNewBlogPost(), current=True,
            icon=self.actionPostBlog.icon())


class WorkspacePeers(TabbedWorkspace):
    def __init__(self, stack):
        super().__init__(stack, WS_PEERS, icon=getIcon('peers.png'),
                         description='Network')

    def setupWorkspace(self):
        from galacteek.ui import chat

        super().setupWorkspace()

        pMgrTab = PeersManager(self.app.mainWindow, self.app.peersTracker)

        # Chat center button
        self.chatCenterButton = chat.ChatCenterButton(
            parent=self.toolBarWsActions)

        self.wsRegisterTab(
            pMgrTab, iPeers(),
            icon=getIcon('peers.png'))

        self.app.mainWindow.atomButton.clicked.connect(self.onShowAtomFeeds)

        self.wsAddWidget(self.app.mainWindow.atomButton)
        self.wsAddWidget(self.chatCenterButton)

    def onShowAtomFeeds(self):
        name = iAtomFeeds()

        tab = self.wsFindTabWithId('dweb-atom-feeds')
        if tab:
            return self.tabWidget.setCurrentWidget(tab)

        tab = AtomFeedsViewTab(self.app.mainWindow)
        self.wsRegisterTab(tab, name,
                           getIcon('atom-feed.png'), current=True)

    async def chatJoinDefault(self):
        chanWidget = await self.chatCenterButton.chans.joinChannel(
            '#galacteek', chanSticky=False)

        self.wsRegisterTab(
            chanWidget,
            '#galacteek',
            icon=getIcon('qta:mdi.chat-outline'),
            current=False
        )


class WorkspaceMisc(TabbedWorkspace):
    def __init__(self, stack):
        super(WorkspaceMisc, self).__init__(
            stack, WS_CONTROL, icon=getIcon('settings.png'),
            description='Settings/Tools'
        )

    @cached_property
    def settingsCenter(self):
        return SettingsCenterTab(self.app.mainWindow, sticky=True)

    def setupWorkspace(self):
        super().setupWorkspace()

        self.wsRegisterTab(
            self.settingsCenter,
            iSettings(),
            icon=getIcon('settings.png')
        )

        self.actionConfigure = self.wsAddCustomAction(
            'config', getIcon('settings.png'),
            iConfigurationEditor(), self.openConfigEditor
        )

        if shutil.which('dot'):
            # Only if we have graphviz's dot
            self.wsAddCustomAction(
                'app-graph', getIcon('ipld.png'),
                'Application graph', partialEnsure(self.openAppGraph)
            )

    @ipfsOp
    async def openAppGraph(self, ipfsop, *args):
        entry = None
        image = await self.app.s.getGraphImagePil()

        if image:
            with TmpFile(suffix='.png') as tfile:
                image.save(tfile.name)
                entry = await ipfsop.addPath(tfile.name)

                await self.app.resourceOpener.open(entry['Hash'])
        else:
            log.debug('Could not generate the app graph')

    def openConfigEditor(self):
        tab = self.wsFindTabWithName(iConfigurationEditor())

        if not tab:
            self.wsRegisterTab(
                ConfigManager(
                    self.app.mainWindow,
                    parent=self
                ),
                iConfigurationEditor(),
                icon=getIcon('settings.png'),
                current=True
            )
        else:
            self.tabWidget.setCurrentWidget(tab)

    def showPinSettings(self):
        pass

    def showSettings(self, showModule: str = None):
        self.tabWidget.setCurrentWidget(self.settingsCenter)

        if showModule:
            self.settingsCenter.selectConfigModule(showModule)


class WorkspaceMessenger(SingleWidgetWorkspace, KeyListener):
    def __init__(self, stack):
        super().__init__(stack, WS_DMESSENGER,
                         icon=getIcon('dmessenger/dmessenger.png'),
                         description='Messenger')

        self.psListen(makeKeyService('net', 'bitmessage'))

    @property
    def bmService(self):
        return services.getByDotName('bitmessage')

    def setupWorkspace(self):
        super().setupWorkspace()

        self.wsSwitchButton.setEnabled(False)

        self.msger = MessengerWidget()
        self.wLayout.addWidget(self.msger)

    async def event_g_services_net_bitmessage(self, key, message):
        log.debug(f'Bitmessage service event: {message}')

        mtype = message['event'].get('type')

        if mtype == 'ServiceStarted':
            await self.msger.setup()
            self.wsSwitchButton.setEnabled(True)
        elif mtype == 'ServiceStopped':
            self.wsSwitchButton.setEnabled(False)

    async def event_g_42(self, key, message):
        if self.msger.bmReady and message['event'] == 'bmComposeRequest':
            self.wsSwitch()

            self.msger.composeMessage(
                message['recipient'],
                subject=message['subject']
            )


class DappSwitchButton(WorkspaceSwitchButton):
    pass


class QMLDappWorkspace(SingleWidgetWorkspace, KeyListener):
    def __init__(self, stack,
                 name,
                 appUri,
                 appComponents,
                 depends,
                 entryPoint: str,
                 iconIpfsPath: IPFSPath,
                 **kwargs):
        super().__init__(stack, name, **kwargs)

        self.components = appComponents
        self.depends = depends
        self.qmlEntryPoint = entryPoint
        self.appWidget = QMLApplicationWidget(appUri, self.qmlEntryPoint)
        self.appUri = appUri
        self.iconPath = iconIpfsPath
        self.wLayout.addWidget(self.appWidget)
        self.dappIcon = None

    @property
    def capService(self):
        return services.getByDotName('core.icapsuledb')

    def createSwitchButton(self, parent=None):
        return DappSwitchButton(self, parent=parent)

    async def loadIcon(self):
        if self.dappIcon:
            self.changeIcon(self.dappIcon)

    @ipfsOp
    async def loadIconOld(self, ipfsop):
        if not self.iconPath.valid:
            return

        icon = await getIconFromIpfs(
            ipfsop, str(self.iconPath), timeout=10)

        if icon and self.wsSwitchButton:
            self.wsSwitchButton.setIcon(icon)

    async def load(self):
        ctx = self.capService.capsuleCtx(self.appUri)
        if not ctx:
            return False

        await self.loadDependencies(ctx)

        if await self.loadComponents(ctx):
            self.appWidget.load()

            return True

        return False

    async def loadDependencies(self, ctx):
        try:
            for dep in ctx.depends:
                depId = dep['id']
                depctx = self.capService.capsuleCtx(depId)

                if not depctx:
                    log.debug(f'{self.appUri}: did not find dep: {dep}')

                    raise Exception(f'{depId}: capsule not found')

                await self.loadComponents(depctx)
        except Exception as err:
            log.debug(f'{self.appUri}: failed to load components: {err}')
            return False
        else:
            return True

    async def loadComponents(self, capsuleCtx):
        try:
            for comp in capsuleCtx.components:
                # Always inside 'qml'

                rootPath = Path(comp['fsPath'])
                dappIconPath = rootPath.joinpath(
                    'share').joinpath('icons').joinpath('dapp.png')

                if dappIconPath.is_file():
                    self.dappIcon = QIcon(QPixmap(str(dappIconPath)))

                qPath = rootPath.joinpath('qml')

                self.appWidget.importComponent(str(qPath))
        except Exception as err:
            traceback.print_exc()
            log.debug(f'{self.appUri}: failed to load components: {err}')
            return False
        else:
            return True
