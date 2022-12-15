import functools

from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QDockWidget
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QSpacerItem
from PyQt5.QtWidgets import QToolBar

from PyQt5.Qt import QSizePolicy

from PyQt5.QtCore import QSize
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QTimer

from galacteek.core import runningApp
from galacteek.core.ps import KeyListener
from galacteek.config import Configurable
from galacteek.config import cWidgetGet
from galacteek.config import cWidgetSetAttr

from ..widgets import SpacingHWidget
from ..widgets import GMediumToolButton
from ..widgets import GLargeToolButton
from ..widgets.toolbar import BasicToolBar
from ..helpers import getIcon
from ..helpers import iconSizeGet

from ..clips import BouncyOrbitClip

from ..dwebspace import *

from . import SpaceDock


class MainDockButton(GLargeToolButton,
                     KeyListener):
    def __init__(self, toolbarWs, icon=None, parent=None):
        super().__init__(icon=icon, parent=parent)

        self.setObjectName('wsMagicianButton')

        self.opened = False
        self.wsCurrent = None

        self.setMinimumSize(QSize(48, 48))
        self.setCheckable(True)

        self.toolbarWs = toolbarWs
        self.toolbarWs.wsSwitched.connect(self.onWsSwitched)
        self.toolbarWs.hovered.connect(self.onHovered)

        self.bouncyClip = BouncyOrbitClip()
        self.bouncyClip.finished.connect(
            functools.partial(self.bouncyClip.start))
        self.bouncyClip.frameChanged.connect(self.onCubeClipFrame)

        self.hovered.connect(self.onHovered)
        self.toggled.connect(self.onToggled)

    def onToggled(self, toggled: bool):
        self.toolbarWs.setProperty('pinned', toggled)

        runningApp().repolishWidget(self.toolbarWs)

    def onHovered(self, hovered: bool):
        self.openUp(hovered)

    def openUp(self, openUp: bool):
        self.setProperty('wsShown', openUp)
        self.toolbarWs.setProperty('wsShown', openUp)

        if openUp:
            self.bouncyClip.start()
        else:
            self.bouncyClip.stop()
            self.setCurrentWsIcon()

        self.opened = openUp

        runningApp().repolishWidget(self.toolbarWs)
        runningApp().repolishWidget(self)

    def setCurrentWsIcon(self):
        if self.wsCurrent and self.wsCurrent.wsIcon:
            self.setIcon(self.wsCurrent.wsIcon)

    def onCubeClipFrame(self, no):
        if self.opened:
            self.setIcon(self.bouncyClip.createIcon())
        else:
            self.setCurrentWsIcon()

    def onWsSwitched(self, workspace):
        if not isinstance(workspace, WorkspaceStatus):
            self.wsCurrent = workspace
            self.setCurrentWsIcon()


class DwebCraftingWidget(QWidget, Configurable):
    configModuleName = 'galacteek.ui.widgets'

    def __init__(self, tbWorkspaces, parent=None):
        super().__init__(parent)

        self.setObjectName('dockCraftingZone')
        self.dock = parent
        self.hLayout = QHBoxLayout(self)
        self.setLayout(self.hLayout)

        self.t1 = QTimer(self)
        self.t1.timeout.connect(self.onTimeout)
        self.spacing = SpacingHWidget()

        self.toolbarWs = tbWorkspaces
        self.toolbarWs.setVisible(False)
        self.toolbarWs.hovered.connect(self.onWsToolbarHovered)
        self.toolbarWsHovered = False
        self.toolbarMisc = BasicToolBar()
        self.toolbarTools = BasicToolBar()
        self.toolbarToolsSep = self.toolbarTools.addSeparator()
        self.toolbarAppStatus = QToolBar(self)
        self.toolbarAppStatus.setIconSize(QSize(24, 24))

        self.dockCommander = MainDockButton(
            self.toolbarWs,
            icon=getIcon('ipfs-cube-64.png')
        )

        if 0:
            self.showHidePyramids = GMediumToolButton(
                icon=getIcon('pyramid-aqua.png'))
            self.showHidePyramids.setCheckable(True)

            self.showHideStatus = GMediumToolButton(
                icon=getIcon('information.png'))
            self.showHideStatus.setCheckable(True)

        self.hLayout.addWidget(self.dockCommander)
        self.hLayout.addWidget(self.toolbarWs)
        self.hLayout.addWidget(self.toolbarMisc)
        # self.hLayout.addWidget(self.showHidePyramids)
        # self.hLayout.addWidget(self.showHideStatus)
        # self.hLayout.addWidget(self.toolbarPyramids)

        self.spacer = QSpacerItem(2, 32, QSizePolicy.Maximum,
                                  QSizePolicy.Maximum)

        self.hLayout.addItem(self.spacer)

        self.hLayout.addWidget(self.toolbarTools)
        self.hLayout.addWidget(self.toolbarAppStatus)

        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed
        )

        self.setMinimumHeight(72)
        self.setMaximumHeight(72)

        self.toolbarWs.setSizePolicy(
            QSizePolicy.MinimumExpanding,
            QSizePolicy.Expanding
        )

        self.toolbarMisc.setSizePolicy(
            QSizePolicy.Minimum,
            QSizePolicy.Expanding
        )

        self.toolbarTools.setSizePolicy(
            QSizePolicy.Maximum,
            QSizePolicy.Expanding
        )

        self.spacerAdjust(QSizePolicy.Expanding)

        self.cApply()
        self.dockCommander.hovered.connect(
            self.onShowHideWorkspaces)

        if 0:
            self.showHidePyramids.toggled.connect(
                self.onShowHidePyramids)
            self.showHideStatus.toggled.connect(
                self.onShowHideAppStatus)

    def config(self):
        return cWidgetGet(
            self.objectName(), mod='galacteek.ui.widgets')

    def configApply(self, cfg):
        if 0:
            self.showHidePyramids.setChecked(
                cfg.toolbarPyramids.visible)
            self.showHideStatus.setChecked(
                cfg.toolbarAppStatus.visible)

            self.toolbarPyramids.setVisible(
                cfg.toolbarPyramids.visible)
            self.toolbarPyramids.setIconSize(
                iconSizeGet(cfg.toolbarPyramids.iconSize))

        self.toolbarAppStatus.setVisible(
            cfg.toolbarAppStatus.visible)

        self.toolbarAppStatus.setIconSize(
            iconSizeGet(cfg.toolbarAppStatus.iconSize))

        self.adjust()
        runningApp().repolishWidget(self)

    def onTimeout(self):
        if not self.toolbarWsHovered and not \
           self.dockCommander.opened and not \
                self.dockCommander.isChecked():
            # self.toolbarWs.setVisible(not self.toolbarWsHovered)
            self.toolbarWs.setVisible(False)

    def onWsToolbarHovered(self, hovered):
        self.toolbarWsHovered = hovered

    def onShowHideWorkspaces(self, checked):
        self.showHideWorkspaces(checked)

    def showHideWorkspaces(self, show: bool):
        if show:
            self.toolbarWs.setVisible(show)
            self.toolbarWs.sizePolicy().setHorizontalPolicy(
                QSizePolicy.MinimumExpanding)
        else:
            self.toolbarWs.sizePolicy().setHorizontalPolicy(
                QSizePolicy.Maximum)

        self.t1.stop()
        self.t1.start(1400)

    def onShowHidePyramids(self, checked):
        cWidgetSetAttr(self.objectName(),
                       'toolbarPyramids.visible',
                       checked,
                       mod='galacteek.ui.widgets')
        self.adjust()

    def onShowHideAppStatus(self, checked):
        cWidgetSetAttr(self.objectName(),
                       'toolbarAppStatus.visible',
                       checked,
                       mod='galacteek.ui.widgets')
        self.adjust()

    def resizeEvent(self, event):
        self.adjust()

        super().resizeEvent(event)

    def adjust(self, checked=None):
        self.spacerAdjust(QSizePolicy.Expanding)

    def spacerAdjust(self, hPolicy, vPolicy=QSizePolicy.Maximum):
        self.spacer.changeSize(1, 1, hPolicy, vPolicy)

    def sizeHintNot(self):
        return QSize(self.width(),
                     self.toolbarWs.height())


class DwebAppDock(SpaceDock, KeyListener, Configurable):
    """
    Main dock
    """

    def __init__(self, tbWs, parent=None):
        super().__init__(parent)

        self.setObjectName('appDock')

        self.cWidget = DwebCraftingWidget(tbWs, parent=self)
        self.setWidget(self.cWidget)
        self.setTitleBarWidget(QWidget())

        self.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self.setContextMenuPolicy(Qt.PreventContextMenu)

    @property
    def tbTools(self):
        return self.cWidget.toolbarTools

    @property
    def tbToolsSep(self):
        return self.cWidget.toolbarToolsSep

    def config(self):
        return cWidgetGet(self.objectName(), mod='galacteek.ui.widgets')

    def addButton(self, widget):
        self.cWidget.toolbarMisc.addWidget(widget)

    def addToolWidget(self, widget):
        self.cWidget.toolbarTools.addWidget(widget)

    def addStatusWidget(self, widget):
        self.cWidget.toolbarAppStatus.addWidget(widget)

    async def event_g_services_app(self, key, message):
        event = message['event']

        if event['type'] == 'QmlApplicationLoaded':
            self.cWidget.showHideWorkspaces(True)
