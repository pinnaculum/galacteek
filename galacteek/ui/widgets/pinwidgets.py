from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QMenu
from PyQt5.QtWidgets import QWidgetAction

from PyQt5.QtQuick import QQuickPaintedItem

from PyQt5.QtCore import QObject
from PyQt5.QtCore import Qt
from PyQt5.QtCore import pyqtSlot

from galacteek import AsyncSignal
from galacteek import partialEnsure
from galacteek import log
from galacteek import ensure
from galacteek import cached_property
from galacteek.config.cmods import pinning as cfgpinning

from galacteek.core import runningApp

from galacteek.ipfs import ipfsOp
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ipfs.cidhelpers import stripIpfs

from galacteek.ui.helpers import getIcon
from galacteek.ui.helpers import messageBox
from galacteek.ui.helpers import messageBoxAsync
from galacteek.ui.i18n import *

from . import PopupToolButton


class PinActions(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sPinPageLinksRequested = AsyncSignal(str)

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

        await ipfsop.ctx.pinner.queue(
            path, recursive, onSuccess,
            qname=self.pinQueueName
        )

    @ipfsOp
    async def unpinPath(self, ipfsop, path):
        log.debug(f'UnPinning object {path}')

        result = await ipfsop.unpin(str(path))
        if result:
            await messageBoxAsync(iUnpinHereOk())

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

    def onUnpin(self):
        if not self.ipfsPath:
            return messageBox(iNotAnIpfsResource())

        ensure(self.unpinPath(self.ipfsPath))

    def onPinPageLinks(self):
        if not self.ipfsPath:
            return messageBox(iNotAnIpfsResource())

        ensure(self.sPinPageLinksRequested.emit(self.ipfsPath))

    def onRpsRegister(self):
        from galacteek.ui.dwebspace import WS_MISC

        wsStack = runningApp().mainWindow.stack

        with wsStack.workspaceCtx(WS_MISC) as ws:
            ws.tabWidget.setCurrentWidget(ws.settingsCenter)
            ws.settingsCenter.selectConfigModule('pinning')

    async def onUnpinFromRps(self, service, *args):
        if not self.ipfsPath or not self.ipfsPath.valid:
            return

        result = await self.rpsUnpin(
            service,
            self.ipfsPath
        )

        if result:
            await messageBoxAsync(iUnpinFromRpsOk())
        else:
            await messageBoxAsync(iUnpinError())

    @ipfsOp
    async def rpsUnpin(self, ipfsop, service, ipfsPath: IPFSPath):
        resolved = await ipfsop.resolve(
            ipfsPath.objPath, recursive=True
        )

        if not resolved:
            return False

        cid = stripIpfs(resolved)

        return await ipfsop.pinRemoteRemove(
            service.serviceName,
            cid=[cid]
        )

    @ipfsOp
    async def onPinToRpsWithName(self, ipfsop, service, *args):
        pass

    async def onPinToRps(self, service, *args):
        if not self.ipfsPath or not self.ipfsPath.valid:
            return

        name = None
        if self.ipfsPath.basename:
            name = self.ipfsPath.basename

        if await self.rpsPin(service, name=name):
            await messageBoxAsync(
                iPinToRpsSuccess(service.serviceName,
                                 str(self.ipfsPath))
            )
        else:
            await messageBoxAsync(
                iPinToRpsError(service.serviceName,
                               str(self.ipfsPath))
            )

    @ipfsOp
    async def rpsPin(self, ipfsop, service, name=None,
                     background=True):
        path = self.ipfsPath.objPath

        if self.ipfsPath.isIpns:
            """
            It's an IPNS path, no worries but resolve it first
            """

            resolved = await ipfsop.nameResolveStreamFirst(
                self.ipfsPath.objPath)
            if resolved:
                path = resolved['Path']

        log.debug(f'RPS pinning object: {path}')

        return await ipfsop.pinRemoteAdd(
            service.serviceName,
            path,
            background=background,
            name=name
        )

    async def onPinToRpsAll(self, *args):
        for srv in cfgpinning.rpsList():
            await self.rpsPin(srv)

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
                runningApp().systemTrayMessage(
                    'PIN', iPinSuccess(str(path)),
                    timeout=2000)
            elif code == 1:
                runningApp().systemTrayMessage(
                    'PIN', iPinError(str(path), msg),
                    timeout=3000)
            elif code == 2:
                # Cancelled, no need to notify here
                pass
            else:
                log.debug('Unknown status code for pinning result')

    def onHelp(self):
        runningApp().manuals.browseManualPage('pinning.html')


class PinObjectButton(PopupToolButton, PinActions):
    ipfsPath: IPFSPath = None
    pinQueueName = 'default'
    mode = 'object'

    @property
    def iconPinRed(self):
        return getIcon('pin/pin-diago-red.png')

    @property
    def iconPinBlue(self):
        return getIcon('pin/pin-diago-blue.png')

    @property
    def iconPillRed(self):
        return getIcon('pin/pill-red.png')

    @property
    def iconPillBlue(self):
        return getIcon('pin/pill-blue.png')

    def changeObject(self, ipfsPath: IPFSPath):
        if not ipfsPath or not ipfsPath.valid:
            self.enableActions(False)
            self.setText(iInvalidObjectPath(str(ipfsPath)))
        else:
            self.ipfsPath = ipfsPath
            self.enableActions(True)
            self.setToolTip(str(ipfsPath))

            self.setText(self.ipfsPath.objPathShort)
            self.setEnabled(True)

    def enableActions(self, enable):
        for action in self.menu.actions():
            action.setEnabled(enable)

    def styleIconOnly(self):
        self.setToolButtonStyle(Qt.ToolButtonIconOnly)

    def styleIconAndText(self):
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

    def setupButton(self):
        self.setObjectName('pinObjectButton')
        self.styleIconOnly()

        iconPin = self.iconPinBlue

        self.actionPinS = QAction(
            iconPin,
            iPinHere(),
            self,
            triggered=self.onPinSingle
        )
        self.actionPinR = QAction(
            iconPin,
            iPinHereRecursive(),
            self,
            triggered=self.onPinRecursive
        )
        self.actionPinRParent = QAction(
            iconPin,
            iPinHereRecursiveParent(),
            self,
            triggered=self.onPinRecursiveParent
        )

        self.actionPinPageLinks = QAction(
            iconPin,
            iPinPageLinks(),
            self,
            triggered=self.onPinPageLinks
        )

        self.actionHelp = QAction(
            getIcon('help.png'),
            iHelp(),
            self,
            triggered=self.onHelp
        )

        self.actionRpsRegister = QAction(
            getIcon('help.png'),
            iRpsRegisterService(),
            self,
            triggered=self.onRpsRegister
        )

        self.actionUnpin = QAction(
            getIcon('cancel.png'),
            iUnpinHere(),
            self,
            triggered=self.onUnpin
        )

        self.enableActions(False)
        self.setEnabled(False)

    async def populateMenuAsync(self, pinMenu):
        # Populate the RPS first
        await self.populateRpsQuick(pinMenu)

        pinMenu.addAction(self.actionPinS)
        pinMenu.addAction(self.actionPinR)
        pinMenu.addSeparator()

        if self.mode == 'web':
            pinMenu.addAction(self.actionPinPageLinks)
            pinMenu.addSeparator()

        pinMenu.addAction(self.actionPinRParent)
        pinMenu.addSeparator()
        pinMenu.addAction(self.actionUnpin)
        pinMenu.addSeparator()

        pinMenu.addAction(self.actionRpsRegister)
        pinMenu.addSeparator()

        pinMenu.addAction(self.actionHelp)

        self.setIcon(self.iconPinBlue)

    async def populateRpsQuick(self, menu):
        srvCount = 0
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

            actionUnpin = QAction(
                getIcon('cancel.png'),
                iUnpinFromRps(srv.displayName),
                self
            )
            actionUnpin.setToolTip(
                iUnpinFromRpsToolTip(srv.displayName))

            actionUnpin.triggered.connect(
                partialEnsure(self.onUnpinFromRps, srv)
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
            menu.addAction(actionUnpin)

            menu.addSeparator()
            # menu.addAction(actionPinC)
            # menu.addSeparator()

            srvCount += 1

        if srvCount > 0:
            menu.addAction(actionPinRpsAll)
            menu.addSeparator()


class QuickItemPinObjectButton(QQuickPaintedItem):
    def __init__(self, parent):
        super().__init__(parent)

        self.button = PinObjectButton()
        self.setRenderTarget(QQuickPaintedItem.FramebufferObject)

    @pyqtSlot(str)
    def change(self, path: str):
        self.button.changeObject(IPFSPath(path))
        self.update()

    def paint(self, painter):
        self.button.render(painter)


class PinObjectAction(QWidgetAction):
    def __init__(self,
                 ipfsPath: IPFSPath = None,
                 pinQueueName='default',
                 buttonStyle='icon',
                 parent=None):
        super().__init__(parent)

        self.setDefaultWidget(self.button)

        self.button.pinQueueName = pinQueueName

        if buttonStyle == 'iconAndText':
            self.button.styleIconAndText()
        elif buttonStyle == 'icon':
            self.button.styleIconOnly()

        if ipfsPath:
            self.button.changeObject(ipfsPath)

    @cached_property
    def button(self):
        return PinObjectButton(parent=self.parent())
