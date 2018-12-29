import copy

from PyQt5.QtWidgets import QWidget, QToolButton, QMenu, QAction, QVBoxLayout
from PyQt5.QtCore import pyqtSignal, QObject, Qt

from galacteek.ipfs.wrappers import ipfsOp
from .helpers import getIcon
from .i18n import iNoTitle


class GalacteekTab(QWidget):
    def __init__(self, gWindow, **kw):
        super(GalacteekTab, self).__init__(gWindow)
        self.vLayout = QVBoxLayout(self)
        self.setLayout(self.vLayout)

        self.gWindow = gWindow
        self.setAttribute(Qt.WA_DeleteOnClose)

    def addToLayout(self, widget):
        self.vLayout.addWidget(widget)

    def onClose(self):
        return True

    @ipfsOp
    async def initialize(self, op):
        pass

    @property
    def app(self):
        return self.gWindow.app

    @property
    def loop(self):
        return self.app.loop

    @property
    def profile(self):
        return self.app.ipfsCtx.currentProfile


class PopupToolButton(QToolButton):
    def __init__(self, icon=None, parent=None, menu=None):
        super(PopupToolButton, self).__init__(parent)

        self.menu = menu if menu else QMenu()
        self.setPopupMode(QToolButton.MenuButtonPopup)
        self.setMenu(self.menu)

        if icon:
            self.setIcon(icon)


class HashmarkMgrButton(PopupToolButton):
    hashmarkClicked = pyqtSignal(str, str)

    def __init__(self, marksLocal, parent=None):
        super(HashmarkMgrButton, self).__init__(parent=parent)

        self.marks = marksLocal
        self.marks.changed.connect(self.onChanged)

        self.cMenus = {}
        self.setIcon(getIcon('hashmarks.png'))
        self.updateMenu()

    def onChanged(self):
        self.updateMenu()

    def updateMenu(self):
        self.menu.clear()

        categories = self.marks.getCategories()

        for category in categories:
            if category not in self.cMenus:
                self.cMenus[category] = QMenu(category)

            menu = self.cMenus[category]
            menu.setIcon(getIcon('stroke-cube.png'))
            marks = self.marks.getCategoryMarks(category)

            def exists(path):
                for action in menu.actions():
                    if action.data()['path'] == path:
                        return action

            for path, mark in marks.items():
                if exists(path):
                    continue

                title = mark['metadata'].get('title', iNoTitle())
                action = QAction(title, self)
                action.setData({
                    'path': path,
                    'mark': copy.copy(mark)
                })
                action.setIcon(getIcon('ipfs-logo-128-white-outline.png'))
                menu.addAction(action)

            menu.triggered.connect(self.linkActivated)
            self.menu.addMenu(menu)

    def linkActivated(self, action):
        data = action.data()
        path, mark = data['path'], data['mark']

        if mark:
            if 'metadata' not in mark:
                return
            self.hashmarkClicked.emit(
                path,
                mark['metadata']['title']
            )
