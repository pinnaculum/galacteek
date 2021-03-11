from PyQt5.QtWidgets import QToolBar
from PyQt5.QtWidgets import QScrollArea
from PyQt5.QtWidgets import QLayout

from PyQt5.QtCore import Qt
from PyQt5.Qt import QSizePolicy

from galacteek.core import runningApp

from . import URLDragAndDropProcessor


class ScrollableToolBar(QToolBar,
                        URLDragAndDropProcessor):
    """
    Scrollable toolbar
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFloatable(True)
        self.setMovable(True)
        # self.setContextMenuPolicy(Qt.PreventContextMenu)

        self.scrollArea = QScrollArea()

        self.scrollArea.setVerticalScrollBarPolicy(
            Qt.ScrollBarAlwaysOn)
        self.scrollArea.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOn)

        self.scrollArea.setAlignment(Qt.AlignVCenter)

        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )

        self.layout().setSizeConstraint(QLayout.SetMinimumSize)
        self.scrollArea.setWidget(self)


class SmartToolBar(QToolBar):
    """
    Scrollable toolbar
    """

    def __init__(self, parent=None, autoExpand=True):
        super().__init__(parent)

        self.entered = False
        self.autoExpand = autoExpand

        self.setFloatable(True)
        self.setMovable(True)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    @property
    def tbActions(self):
        return self.actions()

    @property
    def actionsCount(self):
        return len(self.tbActions)

    def repolish(self):
        runningApp().repolishWidget(self)

    def expand(self, expand=True):
        self.layout().setExpanded(expand)

    def enterEvent(self, event):
        self.entered = True
        super().enterEvent(event)

        if self.actionsCount > 0:
            if self.autoExpand:
                self.expand(True)

            self.setProperty('hovering', True)
            self.repolish()

    def leaveEvent(self, event):
        self.entered = False
        super().leaveEvent(event)

        if self.actionsCount > 0:
            if self.autoExpand:
                self.expand(False)

            self.setProperty('dropping', False)
            self.setProperty('hovering', False)
            self.repolish()

    def dragEnterEvent(self, event):
        URLDragAndDropProcessor.dragEnterEvent(self, event)

        self.setProperty('dropping', True)
        self.repolish()

    def dragLeaveEvent(self, event):
        self.setProperty('dropping', False)
        self.repolish()
