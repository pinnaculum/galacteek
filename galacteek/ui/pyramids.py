import functools
import aioipfs

from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtWidgets import QToolTip
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QToolButton
from PyQt5.QtWidgets import QToolBar
from PyQt5.QtWidgets import QSizePolicy

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import Qt

from PyQt5.QtCore import QPoint

from galacteek import ensure
from galacteek import log
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ipfs.cidhelpers import joinIpns
from galacteek.ipfs import ipfsOp

from .widgets import PopupToolButton
from .widgets import URLDragAndDropProcessor
from .helpers import getMimeIcon
from .helpers import getIcon
from .helpers import getIconFromIpfs
from .helpers import runDialog
from .helpers import questionBox
from .dialogs import AddMultihashPyramidDialog
from .i18n import iUnknown


def iOpenLatestInPyramid():
    return QCoreApplication.translate(
        'pyramidMaster',
        'Open latest item in the pyramid')


def iPopItemFromPyramid():
    return QCoreApplication.translate(
        'pyramidMaster',
        'Pop item off the pyramid')


class MultihashPyramidsToolBar(QToolBar):
    moved = pyqtSignal(int)

    def __init__(self, parent):
        super().__init__(parent)

        self.app = QApplication.instance()
        self.app.marksLocal.pyramidConfigured.connect(self.onPyramidConfigured)
        self.app.marksLocal.pyramidNeedsPublish.connect(self.onPublishPyramid)
        self.app.marksLocal.pyramidChanged.connect(self.onPyramidChanged)

        self.setObjectName('toolbarPyramids')
        self.setToolTip('Hashmark pyramids toolbar')
        self.setContextMenuPolicy(Qt.NoContextMenu)
        self.setFloatable(False)
        self.setMovable(False)
        self.setAcceptDrops(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(400)  # change soon, use parent height on resize
        self.setOrientation(Qt.Vertical)

        pyrIcon = getIcon('pyramid-blue.png')
        self.addPyramidButton = PopupToolButton(
            icon=pyrIcon,
            mode=QToolButton.InstantPopup
        )
        self.addPyramidButton.menu.addAction(
            getIcon('pyramid-aqua.png'),
            'Add multihash pyramid', self.onAddPyramid)
        self.addPyramidButton.menu.addAction(
            pyrIcon, 'Help', self.pyramidHelpMessage)
        self.addWidget(self.addPyramidButton)
        self.addSeparator()

        self.pyramids = {}

    def contextMenuEvent(self, event):
        pass

    def removePyramid(self, pyramidButton, action):
        reply = questionBox(
            'Remove',
            'Remove pyramid <b>{pyr}</b> and its IPNS key ?'.format(
                pyr=pyramidButton.pyramid.name
            )
        )
        if reply is True:
            self.app.marksLocal.pyramidDrop(pyramidButton.pyramid.path)
            self.removeAction(action)
            ensure(self.removeIpnsKey(pyramidButton.pyramid.ipnsKey))
            del pyramidButton

    def pyramidHelpMessage(self):
        QMessageBox.information(
            None,
            'Multihash pyramids',
            'Multihash pyramids allow you to publish IPFS content'
            '(objects) to a fixed IPNS key. Just create a pyramid and '
            'start drag-and-dropping items to the pyramid and they '
            'will automatically be published to the pyramid\'s IPNS key.'
            'You can copy the IPNS key address from the pyramid\'s menu')

    def onPyramidChanged(self, pyramidPath):
        if pyramidPath in self.pyramids:
            self.pyramids[pyramidPath].changed.emit()

    def onPyramidConfigured(self, category, name):
        path = '{0}/{1}'.format(category, name)
        pyramid = self.app.marksLocal.pyramidGet(path)
        if not pyramid:
            return

        button = MultihashPyramidToolButton(pyramid, parent=self)
        action = self.addWidget(button)
        button.deleteRequest.connect(functools.partial(
            self.removePyramid, button, action))
        if pyramid.icon:
            ensure(self.fetchIcon(button, pyramid.icon))
        else:
            button.setIcon(getMimeIcon('unknown'))

        self.pyramids[path] = button

    @ipfsOp
    async def fetchIcon(self, ipfsop, button, iconPath):
        icon = await getIconFromIpfs(ipfsop, iconPath)
        if icon:
            button.setIcon(icon)
        else:
            button.setIcon(getMimeIcon('unknown'))

    def onPublishPyramid(self, pyramidPath, mark):
        pyramid = self.app.marksLocal.pyramidGet(pyramidPath)
        if pyramid and pyramid.ipnsKey:
            ensure(self.publishPyramid(pyramid, mark))

    @ipfsOp
    async def removeIpnsKey(self, ipfsop, ipnsKeyId):
        try:
            key = await ipfsop.keyFindById(ipnsKeyId)
        except aioipfs.APIError:
            # log here
            pass
        else:
            if key:
                log.debug('Removing IPNS key: {}'.format(key))
                await ipfsop.keysRemove(key['Name'])

    @ipfsOp
    async def publishPyramid(self, ipfsop, pyramid, mark):
        try:
            log.debug('{pyramid}: publishing mark {mark} to {ipns}'.format(
                pyramid=pyramid.name,
                mark=mark.path,
                ipns=pyramid.ipnsKey
            ))

            await ipfsop.publish(
                mark.path,
                key=pyramid.ipnsKey,
                allow_offline=pyramid.ipnsAllowOffline,
                lifetime=pyramid.ipnsLifetime,
                timeout=120
            )
        except Exception:
            log.debug('Publish error')
        else:
            self.app.systemTrayMessage(
                'Pyramids',
                'Pyramid {path} was published to IPNS'.format(
                    path=pyramid.path))

    def onAddPyramid(self):
        runDialog(AddMultihashPyramidDialog, self.app.marksLocal,
                  title='New multihash pyramid',
                  parent=self)


class MultihashPyramidToolButton(PopupToolButton):
    deleteRequest = pyqtSignal()
    changed = pyqtSignal()

    def __init__(self, pyramid, icon=None, parent=None):
        super(MultihashPyramidToolButton, self).__init__(
            mode=QToolButton.InstantPopup, parent=parent)
        self.app = QApplication.instance()

        if icon:
            self.setIcon(icon)

        self._pyramid = pyramid
        self.setAcceptDrops(True)
        self.setObjectName('pyramidButton')

        self.changed.connect(self.onPyrChange)
        self.ipfsObjectDropped.connect(self.onObjectDropped)
        self.clicked.connect(self.onOpenLatest)
        self.updateToolTip()

        self.menu.addAction(getIcon('pyramid-aqua.png'),
                            iOpenLatestInPyramid(),
                            self.onOpenLatest)
        self.menu.addSeparator()
        self.menu.addAction(getIcon('pyramid-stack.png'),
                            iPopItemFromPyramid(),
                            self.onPopItem)
        self.menu.addAction(getIcon('clipboard.png'),
                            'Copy IPNS address to clipboard',
                            self.onCopyIpns)
        self.menu.addSeparator()
        self.menu.addAction(
            getIcon('cancel.png'),
            'Remove', lambda: self.deleteRequest.emit())
        self.resetStyleSheet()

    @property
    def pyramid(self):
        return self._pyramid

    def dragEnterEvent(self, event):
        URLDragAndDropProcessor.dragEnterEvent(self, event)
        self.flashToolTip('Pyramid: {path}'.format(path=self.pyramid.path))
        self.setStyleSheet('''
            QToolButton {
                background-color: #EB2121;
            }
        ''')

    def dropEvent(self, event):
        URLDragAndDropProcessor.dropEvent(self, event)
        self.resetStyleSheet()

    def dragLeaveEvent(self, event):
        self.resetStyleSheet()

    def resetStyleSheet(self):
        self.setStyleSheet('''
            QToolButton::hover {
                background-color: #4a9ea1;
            }

            QToolButton::pressed {
                background-color: #eec146;
            }
        ''')

    def flashToolTip(self, message):
        QToolTip.showText(self.mapToGlobal(QPoint(0, 0)), message)

    def updateToolTip(self):
        self.setToolTip('''
            Multihash pyramid: {path}
            Description: {descr}
            Latest: {latest}
        '''.format(
            path=self.pyramid.path,
            descr=self.pyramid.description,
            latest=self.pyramid.latest if self.pyramid.latest else iUnknown()
        ))

    def onPyrChange(self):
        self.updateToolTip()

    def onObjectDropped(self, ipfsPath):
        self.app.marksLocal.pyramidAdd(self.pyramid.path, str(ipfsPath))
        self.updateToolTip()
        self.app.systemTrayMessage(
            'Pyramids',
            'Pyramid {pyr}: registered new hashmark: {path}'.format(
                pyr=self.pyramid.path, path=str(ipfsPath)))

    def onPopItem(self):
        res = self.app.marksLocal.pyramidPop(self.pyramid.path)
        if res is True:
            self.app.systemTrayMessage(
                'Pyramids',
                '{path}: item popped'.format(path=self.pyramid.path))

    def onOpenLatest(self):
        """ Open latest object """
        if not isinstance(self.pyramid.latest, str):
            return

        objPath = IPFSPath(self.pyramid.latest)
        if objPath.valid:
            ensure(self.app.resourceOpener.open(objPath))

    def onCopyIpns(self):
        self.app.setClipboardText(joinIpns(self.pyramid.ipnsKey))
