from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QMenu

from PyQt5.QtCore import QSize
from PyQt5.QtCore import QObject

from galacteek import AsyncSignal
from galacteek import partialEnsure
from galacteek import log
from galacteek import ensure
from galacteek.config.cmods import pinning as cfgpinning

from galacteek.ipfs import ipfsOp
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ui.helpers import getIcon
from galacteek.ui.helpers import messageBox
from galacteek.ui.i18n import *

from . import PopupToolButton


class PinActions(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.spinPageLinksRequested = AsyncSignal(str)

    def pinPath(self, path, recursive=True, notify=True):
        if isinstance(path, str):
            ensure(self.pinQueuePath(path, recursive, notify))
        elif isinstance(path, IPFSPath):
            ensure(self.pinQueuePath(path.objPath, recursive, notify))

    @ipfsOp
    async def pinQueuePath(self, ipfsop, path, recursive, notify):
        log.debug(
            f'Pinning object {path} (recursive: {recursive})')
        onSuccess = None

        # if notify is True:
        #    onSuccess = self.onPinResult

        await ipfsop.ctx.pinner.queue(
            path, recursive, onSuccess,
            qname='browser'
        )

    def onPinSingle(self):
        if not self.ipfsPath:
            return messageBox(iNotAnIpfsResource())

        self.pinPath(self.ipfsPath.objPath, recursive=False)

    def onPinRecursive(self):
        if not self.ipfsPath:
            return messageBox(iNotAnIpfsResource())

        self.pinPath(self.ipfsPath.objPath, recursive=True)

    def onPinRecursiveParent(self):
        if not self.ipfsPath:
            return messageBox(iNotAnIpfsResource())

        parent = self.ipfsPath.parent()

        if parent and parent.valid:
            self.pinPath(parent.objPath, recursive=True)
        else:
            self.pinPath(self.ipfsPath.objPath, recursive=True)

    def onPinPageLinks(self):
        if not self.ipfsPath:
            return messageBox(iNotAnIpfsResource())

        ensure(self.spinPageLinksRequested.emit(self.ipfsPath))

    @ipfsOp
    async def onPinToRpsWithName(self, ipfsop, service, *args):
        pass

    async def onPinToRps(self, service, *args):
        if not self.ipfsPath or not self.ipfsPath.valid:
            return

        name = None
        if self.ipfsPath.basename:
            name = self.ipfsPath.basename

        await self.rpsPin(service, name=name)

    @ipfsOp
    async def rpsPin(self, ipfsop, service, name=None,
                     background=True):
        return await ipfsop.pinRemoteAdd(
            service.serviceName,
            self.ipfsPath.objPath,
            background=background,
            name=name
        )

    async def onPinToRpsAll(self, *args):
        for srv in cfgpinning.rpsList():
            log.debug(f'Pin to RPS all: pinning to {srv}')

            await self.rpsPin(srv, name=name)

    def onPinResult(self, f):
        try:
            path, code, msg = f.result()
        except:
            pass
        else:
            path = IPFSPath(path)
            if not path.valid:
                log.debug('Invalid path in pin result: {}'.format(str(path)))
                return

            if code == 0:
                self.app.systemTrayMessage('PIN', iPinSuccess(str(path)),
                                           timeout=2000)
            elif code == 1:
                self.app.systemTrayMessage('PIN', iPinError(str(path), msg),
                                           timeout=3000)
            elif code == 2:
                # Cancelled, no need to notify here
                pass
            else:
                log.debug('Unknown status code for pinning result')


class PinObjectButton(PopupToolButton, PinActions):
    ipfsPath: IPFSPath = None

    @property
    def iconPinRed(self):
        return getIcon('pin/pin-diago-red.png')

    @property
    def iconPinBlue(self):
        return getIcon('pin/pin-diago-blue.png')

    def changeObject(self, ipfsPath: IPFSPath):
        if not ipfsPath or not ipfsPath.valid:
            self.enableActions(False)
        else:
            self.ipfsPath = ipfsPath
            self.enableActions(True)

    def enableActions(self, enable):
        for action in self.menu.actions():
            action.setEnabled(enable)

    def setupButton(self):
        self.setIconSize(QSize(48, 48))

        iconPin = self.iconPinBlue

        self.actionPinS = QAction(
            iconPin,
            iPinThisPage(),
            self,
            triggered=self.onPinSingle
        )
        self.actionPinR = QAction(
            iconPin,
            iPinRecursive(),
            self,
            triggered=self.onPinRecursive
        )
        self.actionPinRParent = QAction(
            iconPin,
            iPinRecursiveParent(),
            self,
            triggered=self.onPinRecursiveParent
        )

    async def populateMenuAsync(self, pinMenu):
        # Populate the RPS first
        await self.populateRpsQuick(pinMenu)

        pinMenu.addAction(self.actionPinS)
        pinMenu.addAction(self.actionPinR)
        pinMenu.addSeparator()

        pinMenu.addAction(self.actionPinRParent)
        pinMenu.addSeparator()

        self.setIcon(self.iconPinBlue)
        self.enableActions(False)

    async def populateRpsQuick(self, menu):
        actionPinRpsAll = QAction(
            self.iconPinRed,
            iPinToAllRps(),
            self
        )
        actionPinRpsAll.setToolTip(iPinToAllRpsToolTip())

        actionPinRpsAll.triggered.connect(
            partialEnsure(self.onPinToRpsAll)
        )

        for srv in cfgpinning.rpsList():
            actionPinS = QAction(
                self.iconPinRed,
                iPinToRps(srv.displayName),
                self
            )
            actionPinS.setToolTip(
                iPinToRpsToolTip(srv.displayName))

            actionPinS.triggered.connect(
                partialEnsure(self.onPinToRps, srv)
            )

            actionPinC = QAction(
                self.iconPinRed,
                iPinToRpsWithName(srv.displayName),
                self
            )
            actionPinC.setToolTip(
                iPinToRpsToolTip(srv.displayName))

            actionPinC.triggered.connect(
                partialEnsure(self.onPinToRpsWithName, srv)
            )

            sMenu = QMenu(srv.displayName, menu)
            sMenu.setIcon(self.iconPinRed)

            menu.addAction(actionPinS)
            menu.addSeparator()
            menu.addAction(actionPinC)
            menu.addSeparator()

        menu.addAction(actionPinRpsAll)
        menu.addSeparator()
