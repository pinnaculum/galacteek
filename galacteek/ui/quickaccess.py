import asyncio
from rdflib import URIRef

from PyQt5.QtWidgets import QWidgetAction

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import QSize
from PyQt5.QtCore import Qt
from PyQt5.Qt import QSizePolicy

from galacteek import ensure
from galacteek import log
from galacteek.ipfs import ipfsOp
from galacteek.ipfs.stat import StatInfo
from galacteek.ipfs import kilobytes
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.core.ps import KeyListener
from galacteek.ld.rdf.watch import GraphActivityListener

from galacteek.ld.rdf import hashmarks as rdf_hashmarks

from .helpers import getIcon
from .helpers import getMimeIcon
from .helpers import getIconFromIpfs
from .helpers import getIconFromImageData
from .helpers import getIconFromMimeType
from .helpers import getFavIconFromDir
from .widgets.hashmarks import HashmarkToolButton
from .widgets import URLDragAndDropProcessor

from .widgets.toolbar import SmartToolBar

from .i18n import iUnknown
from .i18n import iHashmarkInfoToolTipShort


def iQuickAccess():
    return QCoreApplication.translate(
        'toolbarQa',
        '''<p><b>Quick Access</b> toolbar</p>
           <p>Drag and drop any IPFS content here that
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

        self.qaActions = []

        self.toolbarPyramids = None
        self.app = QCoreApplication.instance()
        self.analyzer = self.app.rscAnalyzer
        self.lock = asyncio.Lock(loop=self.app.loop)

        self.graphsListener = GraphActivityListener(
            watch=['urn:ipg:i:love:hashmarks']
        )
        self.graphsListener.asNeedUpdate.connectTo(
            self.onGraphUpdated
        )

        self.setMovable(True)
        self.setObjectName('qaToolBar')
        self.setToolTip(iQuickAccess())

        self.setAcceptDrops(True)

        self.setOrientation(Qt.Vertical)
        self.orientationChanged.connect(self.onReoriented)

        self.ipfsObjectDropped.connect(self.onIpfsDrop)

    @property
    def smallIcons(self):
        return QSize(32, 32)

    @property
    def largeIcons(self):
        return QSize(64, 64)

    def objectUris(self):
        """
        :rtype: list of uri strings of objects registered
        """
        for action in self.qaActions:
            widget = self.widgetForAction(action)
            if not widget:
                continue

            yield str(widget.hashmark['uri'])

    async def onGraphUpdated(self, graphUri: str):
        await self.load()

    def onReoriented(self, orientation):
        if self.toolbarPyramids:
            self.toolbarPyramids.setOrientation(orientation)

    def attachPyramidsToolbar(self, toolbar):
        self.toolbarPyramids = toolbar
        self.toolbarPyramids.setSizePolicy(
            QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        self.addWidget(self.toolbarPyramids)

    async def save(self):
        pass

    async def load(self):
        try:
            qah = await rdf_hashmarks.searchLdHashmarks(
                extraBindings={
                    'inQADock': URIRef(
                        'urn:glk:ui:docks:qa0'
                    )
                },
                rq='HashmarksSearchForDock'
            )

            uris = list(self.objectUris())

            for hashmark in qah:
                if str(hashmark['uri']) in uris:
                    continue

                ensure(self.registerHashmark(hashmark))
        except Exception as err:
            log.debug(f'Error loading hashmarks: {err}')

    def onIpfsDrop(self, ipfsPath):
        ensure(self.processObject(ipfsPath))

    async def processObject(self, ipfsPath: IPFSPath):
        try:
            mark = await rdf_hashmarks.getLdHashmark(ipfsPath.ipfsUriRef)

            if not mark:
                # todo
                title = ipfsPath.basename if not \
                    ipfsPath.isRoot else iUnknown()

                result = await rdf_hashmarks.addLdHashmark(
                    ipfsPath.ipfsUriRef,
                    title=title
                )

                assert result is True

                mark = await rdf_hashmarks.getLdHashmark(ipfsPath.ipfsUriRef)

            if mark:
                await self.registerHashmark(mark)
        except Exception as err:
            log.debug('Error while processing object: {0} {1}'.format(
                ipfsPath, str(err)))

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
    async def registerHashmark(self, ipfsop,
                               mark,
                               button=None, maxIconSize=512 * 1024):
        markPath = IPFSPath(str(mark['uri']))
        mIcon = IPFSPath(str(mark['iconUrl'])) if mark['iconUrl'] else None
        icon = None
        mimeType, rscStat = None, None

        if markPath.valid:
            mimeType, rscStat = await self.analyzer(str(markPath),
                                                    mimeTimeout=3)

        if mIcon and mIcon.valid:
            icon = await getIconFromIpfs(ipfsop, mIcon.objPath)

            if icon:
                if not await ipfsop.isPinned(mIcon.objPath):
                    log.debug(f'Pinning icon: {mIcon}')

                    await ipfsop.ctx.pin(mIcon.objPath)

        if icon is None:
            if mimeType:
                icon = await self.findIcon(ipfsop, markPath,
                                           rscStat, mimeType)
            else:
                icon = getIcon('unknown-file.png')

        if not button:
            button = HashmarkToolButton(mark, parent=self)
            action = self.addWidget(button)

            button.setToolTip(iHashmarkInfoToolTipShort(mark))

            button.clicked.connect(
                lambda: ensure(self.app.resourceOpener.open(
                    str(mark['uri']), openingFrom='qa')))
            button.deleteRequest.connect(
                lambda: ensure(self.onDelete(button, action)))

            if icon:
                button.setIcon(icon)

            # reg
            self.qaActions.append(action)

            button.setToolTip(iHashmarkInfoToolTipShort(mark))

    async def onDelete(self, button, action):
        # TODO: set RDF show attribute
        try:
            self.removeAction(action)

            del button
        except:
            pass

    async def event_g_services_app(self, key, message):
        event = message['event']

        if event['type'] == 'IpfsRepositoryReady':
            await self.init()

    async def init(self):
        """
        Add some apps and links to the quickaccess bar
        """

        await self.load()

        self.setEnabled(True)


class QuickAccessToolBarAction(QWidgetAction):
    def __init__(self, parent):
        super().__init__(parent)

        self.toolbar = QuickAccessToolBar(parent)
        self.toolbar.setOrientation(Qt.Vertical)
        self.setDefaultWidget(self.toolbar)
