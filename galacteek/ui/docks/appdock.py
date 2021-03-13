from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QDockWidget
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QSpacerItem
from PyQt5.QtWidgets import QToolBar

from PyQt5.Qt import QSizePolicy

from PyQt5.QtCore import QSize
from PyQt5.QtCore import Qt

from galacteek.core import runningApp
from galacteek.config import Configurable
from galacteek.config import cWidgetGet
from galacteek.config import cWidgetSetAttr

from ..widgets import SpacingHWidget
from ..widgets import GMediumToolButton
from ..helpers import getIcon
from ..helpers import iconSizeGet

from . import SpaceDock


class DwebCraftingWidget(QWidget, Configurable):
    configModuleName = 'galacteek.ui.widgets'

    def __init__(self, tbPyramids, parent):
        super().__init__(parent)

        self.setObjectName('dockCraftingZone')
        self.dock = parent
        self.vLayout = QHBoxLayout(self)
        self.setLayout(self.vLayout)

        self.spacing = SpacingHWidget()
        self.toolbarPyramids = tbPyramids
        self.toolbarAppStatus = QToolBar(self)
        self.toolbarAppStatus.setIconSize(QSize(24, 24))

        self.showHidePyramids = GMediumToolButton(
            icon=getIcon('pyramid-aqua.png'))
        self.showHidePyramids.setCheckable(True)

        self.showHideStatus = GMediumToolButton(
            icon=getIcon('information.png'))
        self.showHideStatus.setCheckable(True)

        self.vLayout.addWidget(self.showHidePyramids)
        self.vLayout.addWidget(self.showHideStatus)
        self.vLayout.addWidget(self.toolbarPyramids)

        self.spacer = QSpacerItem(128, 32, QSizePolicy.Maximum,
                                  QSizePolicy.Maximum)

        self.vLayout.addItem(self.spacer)

        self.vLayout.addWidget(self.toolbarAppStatus)

        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed
        )

        self.cApply()
        self.showHidePyramids.toggled.connect(
            self.onShowHidePyramids)
        self.showHideStatus.toggled.connect(
            self.onShowHideAppStatus)

    def config(self):
        return cWidgetGet(
            self.objectName(), mod='galacteek.ui.widgets')

    def configApply(self, cfg):
        self.showHidePyramids.setChecked(
            cfg.toolbarPyramids.visible)
        self.showHideStatus.setChecked(
            cfg.toolbarAppStatus.visible)

        self.toolbarPyramids.setVisible(
            cfg.toolbarPyramids.visible)
        self.toolbarAppStatus.setVisible(
            cfg.toolbarAppStatus.visible)

        self.toolbarPyramids.setIconSize(
            iconSizeGet(cfg.toolbarPyramids.iconSize))
        self.toolbarAppStatus.setIconSize(
            iconSizeGet(cfg.toolbarAppStatus.iconSize))

        self.adjust()
        runningApp().repolishWidget(self)

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
        if self.toolbarPyramids.isVisible():
            self.spacerAdjust(QSizePolicy.Maximum)
        else:
            self.spacerAdjust(QSizePolicy.Expanding)

    def spacerAdjust(self, hPolicy, vPolicy=QSizePolicy.Maximum):
        self.spacer.changeSize(32, 32,
                               hPolicy,
                               vPolicy)

    def sizeHint(self):
        return QSize(self.width(),
                     self.toolbarPyramids.height())

    def sizeHintPerRow(self):
        cfg = self.config()
        maxPerRow = cfg.toolbarPyramids.maxActionsPerRow

        if not self.toolbarPyramids.entered:
            return self.toolbarPyramids.idealShrunkSize(
                maxPerRow)
        else:
            return self.toolbarPyramids.idealExpandedSize(
                maxPerRow)


class DwebCraftingDock(SpaceDock, Configurable):
    """
    Where we craft
    """

    def __init__(self, tbPyramids, parent=None):
        super().__init__(parent)

        self.setObjectName('dockCrafting')

        self.cWidget = DwebCraftingWidget(tbPyramids, self)
        self.setWidget(self.cWidget)
        self.setTitleBarWidget(QWidget())

        self.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self.setContextMenuPolicy(Qt.PreventContextMenu)

    def config(self):
        return cWidgetGet(self.objectName(), mod='galacteek.ui.widgets')

    def addStatusWidget(self, widget):
        self.cWidget.toolbarAppStatus.addWidget(widget)
