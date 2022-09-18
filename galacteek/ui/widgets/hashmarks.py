from galacteek.ld.rdf.hashmarks import *
import aiorwlock
import asyncio
import traceback
from datetime import datetime

from PyQt5.QtWidgets import QToolButton
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QMenu
from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QWidgetAction
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QToolTip

from PyQt5.QtCore import QRect
from PyQt5.QtCore import QEvent
from PyQt5.QtCore import QRegExp
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QSize
from PyQt5.QtCore import QPoint

from PyQt5.QtGui import QRegExpValidator
from PyQt5.QtGui import QKeySequence

from galacteek.ipfs.wrappers import ipfsOp
from galacteek import ensure
from galacteek import partialEnsure
from galacteek import AsyncSignal
from galacteek import services
from galacteek.core.asynclib import asyncify
from galacteek.core.ps import KeyListener
from galacteek.core.ps import makeKeyService

from galacteek import database

from . import GMediumToolButton
from . import PopupToolButton

from ..helpers import getIcon
from ..helpers import getIconFromIpfs
from ..helpers import playSound

from ..i18n import iHashmarksDatabase
from ..i18n import iSearchHashmarks
from ..i18n import iSearchHashmarksAllAcross
from ..i18n import iSearchUseShiftReturn
# from ..i18n import iHashmarkInfoToolTip
from ..i18n import iHashmarkSources


class HashmarkToolButton(GMediumToolButton):
    """
    Used in the quickaccess toolbar
    """
    deleteRequest = pyqtSignal()

    def __init__(self, mark, icon=None, parent=None):
        super(HashmarkToolButton, self).__init__(parent=parent)
        self.setObjectName('qaToolButton')
        if icon:
            self.setIcon(icon)

        self._hashmark = mark

    async def hashmark(self):
        # ??
        return self._hashmark

    def mousePressEvent(self, event):
        button = event.button()

        if button == Qt.RightButton:
            menu = QMenu(self)
            menu.addAction('Remove', lambda: self.deleteRequest.emit())
            menu.exec(self.mapToGlobal(event.pos()))

        super().mousePressEvent(event)


class _HashmarksCommon:
    def makeHashmarkAction(self, mark, loadIcon=True):
        tLenMax = 48

        path = str(mark['uri'])
        title = str(mark['title'])

        if title and len(title) > tLenMax:
            title = '{0} ...'.format(title[0:tLenMax])

        action = QAction(title, self)
        # action.setToolTip(iHashmarkInfoToolTip(mark))

        action.setData({
            'path': path,
            'mark': mark,
            'iconpath': str(mark['iconUrl'])
        })

        if not mark['iconUrl'] or not loadIcon:
            # Default icon
            action.setIcon(getIcon('cube-blue.png'))
        else:
            # ensure(self.loadMarkIcon(action, mark.icon.path))
            pass

        return action

    @ipfsOp
    async def loadMarkIcon(self, ipfsop, action, iconCid):
        data = action.data()

        if isinstance(data, dict) and 'iconloaded' in data:
            return

        icon = await getIconFromIpfs(ipfsop, iconCid)

        if icon:
            await ipfsop.sleep()

            action.setIcon(icon)
            data['iconloaded'] = True
            action.setData(data)


class HashmarksSearchWidgetAction(QWidgetAction):
    pass


class HashmarksSearchLine(QLineEdit):
    """
    The hashmarks search line edit.

    Run the search when Shift + Return is pressed.
    """
    searchRequest = pyqtSignal(str)
    returnNoModifier = pyqtSignal()

    def mouseDoubleClickEvent(self, event):
        event.ignore()

    def keyPressEvent(self, event):
        if event.type() == QEvent.KeyPress:
            modifiers = event.modifiers()
            key = event.key()

            if modifiers & Qt.ShiftModifier:
                if key == Qt.Key_Return:
                    searchText = self.text().strip()
                    if searchText:
                        self.searchRequest.emit(searchText)

                    return
            else:
                if event.key() == Qt.Key_Return:
                    self.returnNoModifier.emit()
                    return

        return super().keyPressEvent(event)


class HashmarksSearcher(PopupToolButton, _HashmarksCommon):
    hashmarkClicked = pyqtSignal(object)

    def __init__(self, iconFile='hashmarks-library.png', parent=None,
                 mode=QToolButton.InstantPopup):
        super(HashmarksSearcher, self).__init__(parent=parent, mode=mode)

        self.app = QApplication.instance()

        self._catalog = {}
        self._sMenus = []
        self.setObjectName('hashmarksSearcher')

        self.setIcon(getIcon(iconFile))
        self.setShortcut(QKeySequence('Ctrl+Alt+h'))

        self.menu.setTitle(iSearchHashmarks())
        self.menu.setIcon(getIcon(iconFile))
        self.menu.setObjectName('hashmarksSearchMenu')
        self.menu.setToolTipsVisible(True)
        self.menu.aboutToShow.connect(self.aboutToShowMenu)
        self.configureMenu()

    @property
    def searchesCount(self):
        return len(self.menu.actions()) - len(self.protectedActions)

    @property
    def protectedActions(self):
        return [self.searchWAction, self.clearAction]

    def isProtectedAction(self, action):
        for pAction in self.protectedActions:
            if action is pAction:
                return True
        return False

    def aboutToShowMenu(self):
        self.searchLine.setFocus(Qt.OtherFocusReason)

    def configureMenu(self):
        self.clearAction = QAction(
            getIcon('clear-all.png'),
            'Clear searches',
            self.menu,
            triggered=self.onClearSearches
        )
        self.clearAction.setEnabled(False)
        self.searchLine = HashmarksSearchLine(self.menu)
        self.searchLine.setObjectName('hLibrarySearch')

        mediumSize = self.fontMetrics().size(0, '*' * (40))
        self.searchLine.setMinimumSize(QSize(mediumSize.width(), 32))
        self.searchLine.setFocusPolicy(Qt.StrongFocus)

        self.searchLine.returnNoModifier.connect(self.onReturnNoShift)
        self.searchLine.searchRequest.connect(self.onSearch)
        self.searchLine.setToolTip(iSearchHashmarksAllAcross())

        self.searchLine.setValidator(
            QRegExpValidator(QRegExp(r"[\w\s@\+\-_./?'\"!#]+")))
        self.searchLine.setMaxLength(96)
        self.searchLine.setClearButtonEnabled(True)

        self.searchWAction = HashmarksSearchWidgetAction(self.menu)
        self.searchWAction.setDefaultWidget(self.searchLine)
        self.menu.addAction(self.searchWAction)
        self.menu.setDefaultAction(self.searchWAction)
        self.menu.addAction(self.clearAction)

    def onReturnNoShift(self):
        QToolTip.showText(self.searchLine.mapToGlobal(
            QPoint(30, self.searchLine.height())),
            iSearchUseShiftReturn(),
            self.searchLine, QRect(0, 0, 0, 0), 1800)

    def onSearch(self, text):
        for action in self.menu.actions():
            if self.isProtectedAction(action):
                continue
            if action.text() == text:
                self.menu.removeAction(action)

        ensure(self.searchInCatalog(text))

    @asyncify
    async def searchInCatalog(self, text):
        from galacteek.core.iptags import ipTagsRFind

        resultsMenu = QMenu(text, self.menu)
        resultsMenu.setToolTipsVisible(True)
        resultsMenu.setObjectName('hashmarksSearchMenu')
        resultsMenu.triggered.connect(
            lambda action: ensure(self.linkActivated(
                action, closeMenu=True)))

        resultsMenu.menuAction().setData({
            'query': text,
            'datecreated': datetime.now()
        })

        showMax = 128
        added = 0

        tags = ipTagsRFind(text)
        if 0:
            if len(tags) > 0:
                await database.hashmarksByTags(
                    tags, defaultPlanet=False
                )

        for hashmark in await searchLdHashmarks(text):
            await asyncio.sleep(0)

            resultsMenu.addAction(self.makeHashmarkAction(hashmark))

            if added > showMax:
                break

            added += 1

        if len(resultsMenu.actions()) > 0:
            self.menu.addMenu(resultsMenu)
            resultsMenu.setIcon(getIcon('search-engine.png'))

        self.clearAction.setEnabled(self.searchesCount > 0)
        self.searchLine.clear()

    def onClearSearches(self):
        for action in self.menu.actions():
            if not self.isProtectedAction(action):
                self.menu.removeAction(action)

        self.clearAction.setEnabled(self.searchesCount > 0)

    def register(self, nodeId, ipfsMarks):
        if nodeId in self._catalog.keys():
            del self._catalog[nodeId]

        self._catalog[nodeId] = ipfsMarks

    async def linkActivated(self, action, closeMenu=False):
        try:
            self.hashmarkClicked.emit(
                action.data()['mark']
            )
            self.searchLine.clear()
            if closeMenu:
                self.menu.hide()
        except Exception:
            traceback.print_exc()


class HashmarksGraphListener(KeyListener):
    psListenKeys = [
        makeKeyService('ld', 'pronto')
    ]

    def __init__(self):
        super().__init__()

        self.asNeedUpdate = AsyncSignal(str)

    async def event_g_services_ld_pronto(self, key, message):
        event = message['event']

        if event['type'] == 'GraphUpdateEvent':
            graphUri = event.get('graphUri')

            if not graphUri.startswith('urn:ipg:i:love:hashmarks'):
                return

            await self.asNeedUpdate.emit(graphUri)


class HashmarksMenu(QMenu):
    def objectPaths(self):
        return [
            action.data()['path'] for action in self.actions()
        ]

    def exists(self, path):
        return path in self.objectPaths()

        for action in menu.actions():
            if action.data()['path'] == path:
                return action


class HashmarkMgrButton(PopupToolButton, _HashmarksCommon,
                        KeyListener):
    hashmarkClicked = pyqtSignal(object)

    def __init__(self, marks, iconFile='hashmarks.png',
                 maxItemsPerCategory=128, parent=None):
        super(HashmarkMgrButton, self).__init__(
            parent=parent,
            mode=QToolButton.InstantPopup
        )

        self.app = QApplication.instance()
        self.searcher = HashmarksSearcher()
        self.lock = aiorwlock.RWLock()

        self.gListener = HashmarksGraphListener()
        self.gListener.asNeedUpdate.connectTo(self.onNeedUpdate)

        self.setObjectName('hashmarksMgrButton')
        self.setIcon(getIcon(iconFile))
        self.setupMenu()

        self.hCount = 0
        self.marks = marks
        self.cMenus = {}
        self.maxItemsPerCategory = maxItemsPerCategory

    @property
    def pronto(self):
        return services.getByDotName('ld.pronto')

    async def onNeedUpdate(self, uri: str):
        print('need update', uri)
        await self.updateMenu()

    def setupMenu(self):
        self.menu.setObjectName('hashmarksMgrMenu')
        self.menu.setToolTipsVisible(True)

        self.sourcesMenu = QMenu(iHashmarkSources())
        self.sourcesMenu.setIcon(self.icon())

        self.menu.addMenu(self.searcher.menu)
        self.menu.addSeparator()

        self.popularTagsMenu = QMenu('Popular Tags')
        self.popularTagsMenu.setObjectName('popularTagsMenu')
        self.popularTagsMenu.setIcon(getIcon('hash.png'))
        self.popularTagsMenu.aboutToShow.connect(
            partialEnsure(self.onShowPopularTags))

        self.menu.addMenu(self.popularTagsMenu)
        self.menu.addSeparator()
        self.app.hmSynchronizer.syncing.connectTo(self.onSynchronizing)

    async def onShowPopularTags(self):
        self.popularTagsMenu.clear()

        tags = await database.hashmarksPopularTags(limit=20)

        for tag in tags:
            menu = QMenu(tag.name, self.popularTagsMenu)
            menu.setIcon(getIcon('ipfs-logo-128-white.png'))
            menu.menuAction().setData(tag)
            menu.triggered.connect(
                lambda action: ensure(self.linkActivated(action)))
            self.popularTagsMenu.addMenu(menu)

            menu.aboutToShow.connect(
                partialEnsure(self.onShowTagHashmarks, menu))

    async def onShowTagHashmarks(self, menu):
        menu.clear()
        menu.setToolTipsVisible(True)
        tag = menu.menuAction().data()

        hashmarks = await database.hashmarksByTags(
            [tag.name], strict=True, limit=30)

        for hashmark in hashmarks:
            await hashmark._fetch_all()
            menu.addAction(self.makeHashmarkAction(hashmark))

    async def onSynchronizing(self, onoff):
        pass

    async def onSynchronize(self):
        pass

    async def updateIcons(self):
        pass

    def tagMenu(self, category):
        if category not in self.cMenus:
            self.cMenus[category] = HashmarksMenu(category)
            self.cMenus[category].setToolTipsVisible(True)
            self.cMenus[category].triggered.connect(
                lambda action: ensure(self.linkActivated(action)))
            self.cMenus[category].setObjectName('hashmarksMgrMenu')
            self.cMenus[category].setIcon(getIcon('cube-orange.png'))
            self.menu.addMenu(self.cMenus[category])

        return self.cMenus[category]

    async def updateMenu(self):
        countAdded = 0
        self.hCount = 0

        async with self.lock.writer_lock:
            # self.pronto.allTagsModel.update()
            tagUris = list(self.pronto.allTagsModel.tagUris())

            for tag in tagUris:
                marks = list(await ldHashmarksByTag(tag))

                menu = self.tagMenu(tag)
                new, initialPaths = [], menu.objectPaths()

                def exists(path):
                    for action in menu.actions():
                        if action.data()['path'] == path:
                            return action

                for hashmark in marks:
                    uri = str(hashmark['uri'])
                    if uri not in initialPaths and uri not in new:
                        menu.addAction(self.makeHashmarkAction(hashmark))
                        countAdded += 1
                        new.append(uri)
                else:
                    menu.hide()

        self.setToolTip(iHashmarksDatabase())

        if countAdded > 0:
            playSound('mime-detected.wav')

    async def linkActivated(self, action):
        try:
            self.hashmarkClicked.emit(
                action.data()['mark']
            )
        except Exception:
            traceback.print_exc()
