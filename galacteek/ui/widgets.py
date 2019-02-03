import copy
import re

from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QToolButton
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QMenu
from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QWidgetAction

from PyQt5.QtCore import pyqtSignal, QObject, Qt
from PyQt5.QtCore import QPoint

from galacteek.ipfs.wrappers import ipfsOp
from .helpers import getIcon
from .i18n import iNoTitle
from .i18n import iHashmarksLibraryCountAvailable
from .i18n import iLocalHashmarksCount


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


class _HashmarksCommon:
    def makeAction(self, path, mark):
        tLenMax = 64
        title = mark['metadata'].get('title', iNoTitle())
        fullTitle = title

        if len(title) > tLenMax:
            title = '{0} ...'.format(title[0:tLenMax])

        action = QAction(title, self)
        action.setToolTip(fullTitle)
        action.setData({
            'path': path,
            'mark': mark
        })
        action.setIcon(getIcon('ipfs-logo-128-white-outline.png'))
        return action


class HashmarkMgrButton(PopupToolButton, _HashmarksCommon):
    hashmarkClicked = pyqtSignal(str, str)

    def __init__(self, marks, iconFile='hashmarks.png',
                 maxItemsPerCategory=128, parent=None):
        super(HashmarkMgrButton, self).__init__(parent=parent)

        self.menu.setObjectName('hashmarksMgrMenu')
        self.hCount = 0
        self.marks = marks
        self.cMenus = {}
        self.maxItemsPerCategory = maxItemsPerCategory
        self.setIcon(getIcon(iconFile))

        try:
            self.marks.changed.disconnect(self.onChanged)
        except:
            pass

        self.marks.changed.connect(self.onChanged)
        self.updateMenu()

    def onChanged(self):
        self.updateMenu()

    def updateMenu(self):
        self.hCount = 0
        categories = self.marks.getCategories()

        for category in categories:
            marks = self.marks.getCategoryMarks(category)
            mItems = marks.items()
            mDisplayC = min(len(mItems), self.maxItemsPerCategory)

            if len(mItems) not in range(1, self.maxItemsPerCategory):
                continue

            if category not in self.cMenus:
                self.cMenus[category] = QMenu(category)
                self.cMenus[category].triggered.connect(self.linkActivated)
                self.cMenus[category].setObjectName('hashmarksMgrMenu')
                self.menu.addMenu(self.cMenus[category])

            menu = self.cMenus[category]
            menu.setIcon(getIcon('stroke-cube.png'))

            def exists(path):
                for action in menu.actions():
                    if action.data()['path'] == path:
                        return action

            if len(mItems) in range(1, self.maxItemsPerCategory):
                for path, mark in mItems:
                    self.hCount += 1

                    if exists(path):
                        continue

                    menu.addAction(self.makeAction(path, mark))
            else:
                menu.hide()

        self.setToolTip(iLocalHashmarksCount(self.hCount))

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


class HashmarksLibraryButton(PopupToolButton, _HashmarksCommon):
    hashmarkClicked = pyqtSignal(str, str)

    def __init__(self, iconFile='hashmarks-library.png',
                 maxItemsPerCategory=32, parent=None):
        super(HashmarksLibraryButton, self).__init__(parent=parent)

        self.cMenus = {}
        self.hCount = 0
        self.maxItemsPerCategory = maxItemsPerCategory
        self.setIcon(getIcon(iconFile))
        self.menu.setObjectName('hashmarksLibraryMenu')
        self.searchMenu = None
        self.addSearchMenu()

    def addSearchMenu(self):
        if self.searchMenu is not None:
            return

        self.searchMenu = QMenu('Search')
        self.menu.addMenu(self.searchMenu)

        self.searchLine = QLineEdit()
        self.searchLine.returnPressed.connect(self.onSearch)
        self.searchWAction = QWidgetAction(self)
        self.searchWAction.setDefaultWidget(self.searchLine)
        self.searchMenu.addAction(self.searchWAction)
        self.searchMenu.setEnabled(False)

    def onSearch(self):
        pos = self.searchLine.mapToGlobal(QPoint(0, 0))
        text = self.searchLine.text()

        resultsMenu = QMenu()
        resultsMenu.triggered.connect(
            lambda action: self.linkActivated(
                action, closeMenu=True))
        self.searchTextInMenu(self.menu, text, resultsMenu)
        resultsMenu.exec(pos)

    def searchTextInMenu(self, menu, text, rMenu):
        for action in menu.actions():
            menu = action.menu()
            if menu:
                self.searchTextInMenu(menu, text, rMenu)
            else:
                data = action.data()
                if not isinstance(data, dict):
                    continue

                path = data['path']
                mark = data['mark']

                maTitle = re.search(text, mark['metadata']['title'],
                                    re.IGNORECASE)
                maDesc = re.search(text, mark['metadata']['description'],
                                   re.IGNORECASE)
                if maTitle or maDesc:
                    rMenu.addAction(self.makeAction(path, mark))

    def updateMenu(self, ipfsMarks):
        categories = ipfsMarks.getCategories()

        for category in categories:
            marks = ipfsMarks.getCategoryMarks(category)
            mItems = marks.items()

            if len(mItems) not in range(1, self.maxItemsPerCategory):
                continue

            if category not in self.cMenus:
                self.cMenus[category] = QMenu(category)
                self.cMenus[category].triggered.connect(self.linkActivated)
                self.cMenus[category].setObjectName('hashmarksLibraryMenu')
                self.menu.addMenu(self.cMenus[category])

            menu = self.cMenus[category]

            menu.setIcon(getIcon('stroke-cube.png'))

            def exists(path):
                for action in menu.actions():
                    if action.data()['path'] == path:
                        return action

            for path, mark in mItems:
                self.hCount += 1
                if exists(path):
                    continue

                action = self.makeAction(path, mark)
                menu.addAction(action)

        self.setToolTip(iHashmarksLibraryCountAvailable(self.hCount))
        if self.hCount > 0:
            self.searchMenu.setEnabled(True)

    def linkActivated(self, action, closeMenu=False):
        data = action.data()
        path, mark = data['path'], data['mark']

        if mark:
            if 'metadata' not in mark:
                return

            self.hashmarkClicked.emit(
                path,
                mark['metadata']['title']
            )

            if closeMenu:
                self.menu.hide()
