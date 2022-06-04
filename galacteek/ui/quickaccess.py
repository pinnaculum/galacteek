import asyncio

from PyQt5.QtWidgets import QWidgetAction

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import QSize
from PyQt5.QtCore import Qt
from PyQt5.Qt import QSizePolicy

from galacteek import ensure
from galacteek import log
from galacteek import database
from galacteek.ipfs import ipfsOp
from galacteek.ipfs.stat import StatInfo
from galacteek.ipfs import kilobytes
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.core.ps import KeyListener

from .helpers import getIcon
from .helpers import getMimeIcon
from .helpers import getIconFromIpfs
from .helpers import getIconFromImageData
from .helpers import getIconFromMimeType
from .helpers import getFavIconFromDir
from .widgets import HashmarkToolButton
from .widgets import QAObjTagItemToolButton
from .widgets import URLDragAndDropProcessor

from .widgets.toolbar import SmartToolBar

from .i18n import iUnknown
from .i18n import iHashmarkInfoToolTipShort


def iQuickAccess():
    return QCoreApplication.translate(
        'toolbarQa',
        '''<p><b>Quick Access</b> toolbar</p>
           <p>Drag and drop hashmarks and IPFS objects that
           you want to have easy access to</p>
        ''')


class QuickAccessToolBar(SmartToolBar,
                         URLDragAndDropProcessor,
                         KeyListener):
    """
    Quick Access toolbar, child of the main toolbar
    """

    def __init__(self, parent=None):
        SmartToolBar.__init__(self, parent)
        URLDragAndDropProcessor.__init__(self)
        KeyListener.__init__(self)

        self.toolbarPyramids = None
        self.app = QCoreApplication.instance()
        self.analyzer = self.app.rscAnalyzer
        self.lock = asyncio.Lock(loop=self.app.loop)

        self.setMovable(True)
        self.setObjectName('qaToolBar')
        self.setToolTip(iQuickAccess())

        self.setAcceptDrops(True)

        self.setOrientation(Qt.Vertical)
        self.orientationChanged.connect(self.onReoriented)

        database.QATagItemConfigured.connectTo(self.qaTagItemConfigured)

        self.ipfsObjectDropped.connect(self.onIpfsDrop)

    @property
    def smallIcons(self):
        return QSize(32, 32)

    @property
    def largeIcons(self):
        return QSize(64, 64)

    def onReoriented(self, orientation):
        if self.toolbarPyramids:
            self.toolbarPyramids.setOrientation(orientation)

    def attachPyramidsToolbar(self, toolbar):
        self.toolbarPyramids = toolbar
        self.toolbarPyramids.setSizePolicy(
            QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        self.addWidget(self.toolbarPyramids)

    def sizeHintUnused(self):
        try:
            actionsCount = len(self.actions())
            pages = actionsCount / 12
        except Exception:
            pass

        return QSize(
            max(3, pages) * (self.iconSize().width()),
            self.height()
        )

    async def save(self):
        pass

    async def load(self):
        try:
            for item in await database.qaHashmarkItems():
                ensure(self.registerHashmark(item.ithashmark))
        except Exception as err:
            log.debug(str(err))

    async def registerDefaults(self):
        # Register some default hashmarks using object tags
        await self.registerFromObjTag('#dapp-hardbin')
        await self.registerFromObjTag('#dapp-ipfessay')
        await self.registerFromObjTag('#wikipedia-en')

    def onIpfsDrop(self, ipfsPath):
        ensure(self.processObject(ipfsPath))

    async def processObject(self, ipfsPath):
        path = str(ipfsPath)

        try:
            mark = await database.hashmarksByPath(path)
            if not mark:
                title = ipfsPath.basename if not \
                    ipfsPath.isRoot else iUnknown()
                mark = await database.hashmarkAdd(
                    path, title=title,
                    tags=['#quickaccess']
                )

            res = await database.QAHashmarkItem.filter(
                ithashmark__id=mark.id).first()
            if not res:
                item = database.QAHashmarkItem(ithashmark=mark)
                await item.save()

            await self.registerHashmark(mark)
        except Exception as err:
            log.debug('Error while processing object: {0} {1}'.format(
                ipfsPath, str(err)))

    async def registerFromObjTag(self, tag):
        try:
            await database.qaTagItemAdd(tag)
        except Exception:
            log.debug('Could not register hashmark with tag: {}'.format(
                tag))

    async def findIcon(self, ipfsop, ipfsPath, rscStat, mimeType,
                       maxIconSize=kilobytes(512)):
        icon = None
        statInfo = StatInfo(rscStat)

        if statInfo.valid and mimeType.isImage:
            if statInfo.dataSmallerThan(maxIconSize):
                await ipfsop.sleep()

                data = await ipfsop.catObject(str(ipfsPath), timeout=5)
                if data:
                    icon = getIconFromImageData(data)
            else:
                icon = getMimeIcon('image/x-generic')
        elif mimeType.isDir:
            favIcon = await getFavIconFromDir(ipfsop, ipfsPath)
            if favIcon:
                icon = favIcon
            else:
                icon = getMimeIcon('inode/directory')
        else:
            await ipfsop.sleep()
            icon = getIconFromMimeType(mimeType)

        if icon is None:
            icon = getIcon('unknown-file.png')

        return icon

    @ipfsOp
    async def registerHashmark(self, ipfsop, mark,
                               button=None, maxIconSize=512 * 1024):
        """
        Register an object in the toolbar with an associated hashmark
        """

        await mark._fetch_all()

        ipfsPath = IPFSPath(mark.path)
        if not ipfsPath.valid:
            return

        result = await self.analyzer(ipfsPath, mimeTimeout=5)
        if result is None:
            return

        mimeType, rscStat = result

        mIcon = mark.icon.path if mark.icon else None
        icon = None

        if mIcon and IPFSPath(mIcon).valid:
            stat = await ipfsop.objStat(mIcon)

            statInfo = StatInfo(stat)

            # Check filesize from the stat on the object
            if statInfo.valid and statInfo.dataSmallerThan(maxIconSize):
                icon = await getIconFromIpfs(ipfsop, mIcon)

                if icon is None:
                    icon = getIcon('unknown-file.png')
                else:
                    if not await ipfsop.isPinned(mIcon):
                        log.debug('Pinning icon {0}'.format(mIcon))
                        await ipfsop.ctx.pin(mIcon)
        elif mimeType:
            icon = await self.findIcon(ipfsop, ipfsPath, rscStat, mimeType)
        else:
            icon = getIcon('unknown-file.png')

        if not button:
            button = HashmarkToolButton(mark, parent=self, icon=icon)
            action = self.addWidget(button)
            button.setToolTip(iHashmarkInfoToolTipShort(mark))
            button.clicked.connect(
                lambda: ensure(self.app.resourceOpener.open(
                    str(ipfsPath), openingFrom='qa')))
            button.deleteRequest.connect(
                lambda: ensure(self.onDelete(button, action)))
        else:
            if icon:
                button.setIcon(icon)

            button.setToolTip(iHashmarkInfoToolTipShort(mark))

    async def onDelete(self, button, action):
        try:
            self.removeAction(action)
        except:
            pass
        else:
            hashmark = await button.hashmark()

            res = await database.QAHashmarkItem.filter(
                ithashmark__id=hashmark.id).first()
            if res:
                await res.delete()

            del button

    @ipfsOp
    async def qaTagItemConfigured(self, ipfsop, qaItem):
        icon = getIcon('unknown-file.png')
        button = QAObjTagItemToolButton(qaItem, parent=self, icon=icon)
        action = self.addWidget(button)
        button.deleteRequest.connect(
            lambda: ensure(self.onDelete(button, action)))

        hashmark = await button.hashmark()

        if hashmark:
            await hashmark._fetch_all()
            ensure(self.registerHashmark(hashmark, button=button))

    async def event_g_services_app(self, key, message):
        event = message['event']

        if event['type'] == 'IpfsRepositoryReady':
            await self.init()

    async def init(self):
        """
        Add some apps and links to the quickaccess bar
        """

        await self.registerDefaults()
        await self.load()

        self.setEnabled(True)


class QuickAccessToolBarAction(QWidgetAction):
    def __init__(self, parent):
        super().__init__(parent)

        self.toolbar = QuickAccessToolBar(parent)
        self.toolbar.setOrientation(Qt.Vertical)
        self.setDefaultWidget(self.toolbar)
