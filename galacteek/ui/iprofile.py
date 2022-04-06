import random

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import QPoint
from PyQt5.QtCore import QRect
from PyQt5.QtCore import QUrl
from PyQt5.QtCore import QSize
from PyQt5.QtCore import Qt

from PyQt5.QtWidgets import QMenu
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QToolButton
from PyQt5.QtWidgets import QToolTip
from PyQt5.QtWidgets import QActionGroup
from PyQt5.QtWidgets import QAction

from PyQt5.QtGui import QPixmap
from PyQt5.QtGui import QImage

from galacteek import ensure
from galacteek import partialEnsure
from galacteek import log
from galacteek.ipfs.wrappers import ipfsOp
from galacteek.ipfs.cidhelpers import joinIpns
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.core.iphandle import ipHandleGen
from galacteek.core.iphandle import SpaceHandle

from galacteek.crypto.qrcode import IPFSQrEncoder

from galacteek.ipfs.pubsub import TOPIC_PEERS
from galacteek.ipfs.pubsub.messages.core import PeerIpHandleChosen

from .chat import ChatChannels
from .dialogs import UserProfileInitDialog
from .dids import buildIpServicesMenu
from .helpers import filesSelectImages
from .helpers import getIcon
from .helpers import runDialogAsync
from .clips import RotatingCubeClipSimple
from .widgets import PopupToolButton
from .forms import ui_profileeditdialog
from .i18n import iUnknown
from .i18n import iIPServices


def iNoSmartContract():
    return QCoreApplication.translate(
        'GalacteekWindow',
        '''<p>
            Could not load Ethereum contract!
            Check your Ethereum connection settings
           </p>

            <p>
            Create an account at <a href="https://infura.io">infura.io</a>
            and change the Ethereum RPC URL in the Ethereum settings.
           </p>
           <p>
           For now you'll be limited to create a temporary DID.
           </p>
        ''')


def iIdentityInfo(vPlanet, ipHandle, did):
    return QCoreApplication.translate(
        'GalacteekWindow',
        '''<p>
             <img src=':/share/icons/helmet.png'
                width="32" height="32" />
           </p>
           <p>
            IP handle: <b>{1}</b>
           </p>
           <p>
            DID: <b>{2}</b>
           </p>
        ''').format(vPlanet.lower() if vPlanet else iUnknown(), ipHandle, did)


class ProfileButton(PopupToolButton):
    def __init__(self, **kw):
        super(ProfileButton, self).__init__(
            mode=QToolButton.InstantPopup,
            **kw
        )
        self.app = QApplication.instance()
        self.setEnabled(False)
        self.curProfile = None
        self.setObjectName('profileButton')

        self.sMenu = QMenu(iIPServices(), self.menu)
        self.sMenu.setToolTipsVisible(True)
        self.sMenu.setIcon(getIcon('ipservice.png'))
        self.menu.addMenu(self.sMenu)

        self.setupStatusMenu()

    def setupStatusMenu(self):
        self.statusMenu = QMenu('Status', self.menu)
        self.statusMenu.setIcon(getIcon('lifeline-arrow.png'))

        self.pStatusGroup = QActionGroup(self)
        self.pStatusGroup.triggered.connect(self.onStatusChanged)

        for idx, status in enumerate(
                ['Available', 'Sleeping', 'Busy', 'Away', 'In a meeting']):
            action = QAction(status, self.pStatusGroup)
            action.setCheckable(True)
            if idx == 0:
                action.setChecked(True)

            self.pStatusGroup.addAction(action)

        self.statusMenu.addActions(self.pStatusGroup.actions())
        self.menu.addSeparator()
        self.menu.addMenu(self.statusMenu)

    def onStatusChanged(self, action):
        if not self.curProfile:
            return

        self.curProfile._status = action.text()

    async def changeProfile(self, profile):
        self.curProfile = profile
        self.updateToolTip(self.curProfile)

        profile.userInfo.changed.connect(self.onInfoChanged)
        profile.identityChanged.connectTo(self.onIdentityChanged)

        if profile.userWebsite:
            profile.userWebsite.websiteUpdated.connectTo(
                self.onWebsiteUpdated
            )

        if not profile.userInfo.iphandle:
            QToolTip.showText(
                self.mapToGlobal(
                    QPoint(0, 16)),
                "Your profile is not initialized yet",
                self, QRect(0, 0, 0, 0), 1800
            )

        ipid = await self.curProfile.userInfo.ipIdentifier()
        if ipid:
            await buildIpServicesMenu(ipid, self.sMenu, parent=self.menu)
            ipid.sChanged.connectTo(self.onDidChanged)

    async def onDidChanged(self, docCid: str):
        await self.rebuildServicesMenu()

    async def onIdentityChanged(self, identityUid: str, personDid: str):
        log.debug('Identity changed to DID {}'.format(personDid))
        await self.rebuildServicesMenu()

    async def rebuildServicesMenu(self):
        ipid = await self.curProfile.userInfo.ipIdentifier()
        if ipid:
            log.debug('Regenerating IP services menu')
            self.sMenu.clear()
            await buildIpServicesMenu(ipid, self.sMenu, parent=self.menu)

    def onInfoChanged(self):
        ensure(self.curProfile.userWebsite.updateAboutPage())
        self.updateToolTip(self.curProfile)

    def updateToolTip(self, profile):
        spaceHandle = SpaceHandle(profile.userInfo.iphandle)

        self.setToolTip(iIdentityInfo(
            profile.userInfo.vplanet,
            spaceHandle.human if spaceHandle.valid else iUnknown(),
            profile.userInfo.personDid
        ))

    async def onWebsiteUpdated(self):
        self.setStyleSheet('''
            QToolButton {
                background-color: #B7CDC2;
            }
        ''')
        self.app.loop.call_later(
            3, self.setStyleSheet,
            'QToolButton {}'
        )


class ProfileEditDialog(QDialog):
    def __init__(self, profile, parent=None):
        super().__init__(parent)

        self.setObjectName('profileEditDialog')
        self.app = QApplication.instance()
        self.profile = profile

        self.ui = ui_profileeditdialog.Ui_ProfileEditDialog()
        self.ui.setupUi(self)
        self.ui.pEditTabWidget.setCurrentIndex(0)

        self.updateProfile()

        self.ui.labelWarning.setStyleSheet(
            'QLabel { font-weight: bold; }')
        self.ui.labelInfo.setStyleSheet(
            'QLabel { font-weight: bold; }')
        self.ui.labelWarning.linkActivated.connect(
            self.onLabelAnchorClicked
        )

        self.ui.profileDid.setText('<b>{0}</b>'.format(
            self.profile.userInfo.personDid))

        self.ui.lockButton.toggled.connect(self.onLockChange)
        self.ui.lockButton.setChecked(True)
        self.ui.changeIconButton.clicked.connect(self.changeIcon)
        self.ui.closeButton.clicked.connect(self.close)
        self.ui.generateIdentityButton.clicked.connect(
            partialEnsure(self.onNewIdentity))

        self.reloadIcon()

    async def onNewIdentity(self, *args):
        dlg = UserProfileInitDialog(showCancel=True)
        await runDialogAsync(dlg)
        options = dlg.options()

        if dlg.result() == 1:
            chatChannels = ChatChannels()
            chatChannels.leaveAllChannels()

            self.enableDialog(toggle=False)

            clip = RotatingCubeClipSimple()
            clip.setScaledSize(QSize(48, 48))
            clip.start()

            self.ui.labelInfo.setAlignment(Qt.AlignCenter)
            self.ui.labelInfo.setMovie(clip)

            try:
                await self.createIdentity(options)
            except Exception as err:
                self.infoMessage(f'Error creating identity: {err}')

            self.enableDialog(toggle=True)

    @ipfsOp
    async def createIdentity(self, ipfsop, options):
        curProfile = ipfsop.ctx.currentProfile
        curProfile._initOptions = options

        username = options['username']
        vPlanet = options['vPlanet']

        if not username or not vPlanet:
            raise Exception('No handle specified')

        for iphandle in self.peeredIpHandlesGen(
                ipfsop.ctx.node.id,
                vPlanet, username):
            avail, qrRaw, qrPng = await self.localHandleAvailable(
                iphandle)
            if avail:
                await self.ipHandleLockIpfs(ipfsop, iphandle, qrRaw, qrPng)

                await self.profile.createIpIdentifier(
                    iphandle=iphandle,
                    updateProfile=True,
                    peered=True
                )

                break

        async with self.profile.userInfo as dag:
            dag.curIdentity['username'] = username
            dag.curIdentity['vplanet'] = vPlanet
            dag.curIdentity['iphandle'] = iphandle

        self.infoMessage('Your IP handle and DID were updated')
        self.updateProfile()
        curProfile._initOptions = {}
        return True

    def enableDialog(self, toggle=True):
        self.ui.pEditTabWidget.setEnabled(toggle)
        self.setEnabled(toggle)

    def onLockChange(self, toggled):
        self.ui.pEditTabWidget.setEnabled(not toggled)

    def onLabelAnchorClicked(self, url):
        self.app.mainWindow.addBrowserTab().enterUrl(QUrl(url))

    def infoMessage(self, text):
        self.ui.labelInfo.setText(text)

    def updateProfile(self):
        spaceHandle = SpaceHandle(self.profile.userInfo.iphandle)

        if spaceHandle.valid:
            self.ui.ipHandle.setText(
                '<b>{0}</b>'.format(str(spaceHandle)))

            self.ui.profileDid.setText('<b>{0}</b>'.format(
                self.profile.userInfo.personDid))
        else:
            self.ui.ipHandle.setText(iUnknown())
            self.ui.profileDid.setText('<b>{0}</b>'.format(iUnknown()))

    def reloadIcon(self):
        ensure(self.loadIcon())

    async def loadIcon(self):
        ipIdentifier = await self.profile.userInfo.ipIdentifier()
        avatarService = await ipIdentifier.avatarService()

        if avatarService:
            avatar = await avatarService.endpointCat()

            if isinstance(avatar, bytes):
                try:
                    img1 = QImage()
                    img1.loadFromData(avatar)
                    img = img1.scaledToWidth(128)
                    self.ui.iconPixmap.setPixmap(QPixmap.fromImage(img))
                except Exception as err:
                    log.debug(str(err))

    def changeIcon(self):
        fps = filesSelectImages()
        if len(fps) > 0:
            ensure(self.setIcon(fps.pop()))

    @ipfsOp
    async def setIcon(self, op, fp):
        entry = await op.addPath(fp, recursive=False)
        if not entry:
            return

        async with self.profile.userInfo as dag:
            dag.curIdentity['avatar'] = dag.mkLink(entry['Hash'])

        # Update the avatar DID service
        ipid = await self.profile.userInfo.ipIdentifier()

        await ipid.avatarSet(IPFSPath(entry['Hash']))
        await op.sleep(1)
        await self.loadIcon()

    async def ipHandleLockIpfs(self, ipfsop, iphandle, qrRaw, qrPng):
        profile = ipfsop.ctx.currentProfile

        msg = PeerIpHandleChosen.make(
            ipfsop.ctx.node.id,
            iphandle,
            None,
            qrPng['Hash'],
        )

        async with profile.userInfo as userInfo:
            userInfo.curIdentity['iphandleqr']['png'] = userInfo.mkLink(qrPng)

        if not self.app.offline:
            await ipfsop.ctx.pubsub.send(TOPIC_PEERS, msg)

    @ipfsOp
    async def encodeIpHandleQr(self, ipfsop, iphandle, format='raw',
                               filename=None):
        encoder = IPFSQrEncoder()

        try:
            entry = await ipfsop.addString(iphandle, only_hash=True)
            if not entry:
                return

            encoder.add(entry['Hash'])
            encoder.add(self.profile.userInfo.personDid)
            encoder.add(joinIpns(ipfsop.ctx.node.id))
            return await encoder.encodeAndStore(format=format)
        except Exception:
            # TODO
            pass

    def setLimitedControls(self):
        self.ui.labelWarning.setText(iNoSmartContract())

    def getIpHandlesOp(self):
        return self.app.ethereum.getDefaultLoadedOperator('iphandles')

    @ipfsOp
    async def ipHandleAvailable(self, ipfsop, iphandle):
        cOperator = self.getIpHandlesOp()

        exists = await cOperator.ipHandleExists(iphandle)

        rawQr = await self.encodeIpHandleQr(
            iphandle, filename=iphandle, format='raw')
        rawQrPng = await self.encodeIpHandleQr(
            iphandle, filename=iphandle, format='png')
        return not exists, rawQr, rawQrPng

    @ipfsOp
    async def localHandleAvailable(self, ipfsop, iphandle):
        log.debug('Checking if {} is available ..'.format(iphandle))

        if await self.profile.userInfo.ipHandleExists(iphandle) is True:
            log.debug(f'{iphandle} is already registered ..')
            return (False, None, None)

        qrPng = await self.profile.userInfo.encodeIpHandleQr(
            iphandle,
            self.profile.userInfo.personDid
        )

        if not qrPng:
            log.debug(f'{iphandle}: QR is empty ..')
            return (False, None, None)

        providers = await ipfsop.whoProvides(qrPng['Hash'], timeout=5)
        log.debug('Providers: {!r}'.format(providers))

        def isOurself(providers):
            if len(providers) == 1:
                for prov in providers:
                    if prov.get('ID') == ipfsop.ctx.node.id:
                        return True
            return False

        if len(providers) == 0 or isOurself(providers):
            await ipfsop.addString(iphandle)
            return (True, None, qrPng)
        else:
            return (False, None, None)

    def ipHandlesGen(self, vPlanet, username,
                     onlyrand=False, randcount=9):
        r = random.Random()

        if not onlyrand:
            yield '{user}@{planet}'.format(
                planet=vPlanet,
                user=username
            )

        for att in range(0, randcount):
            yield '{user}#{rid}@{planet}'.format(
                planet=vPlanet,
                user=username,
                rid=str(r.randint(1, 199))
            )

    def peeredIpHandlesGen(self, peerId, vPlanet, username,
                           onlyrand=False, randcount=9):
        yield ipHandleGen(username, vPlanet, peerId=peerId)

        for att in range(0, randcount):
            yield ipHandleGen(username, vPlanet, peerId=peerId, rand=True)

    @ipfsOp
    async def generatePeeredIdentity(self, ipfsop):
        username = self.ui.username.text().strip()
        vPlanet = self.ui.vPlanet.currentText()

        if not self.app.offline:
            await ipfsop.ctx.pubsub.services[TOPIC_PEERS].sendLogoutMessage()

        for iphandle in self.peeredIpHandlesGen(
                ipfsop.ctx.node.id,
                vPlanet, username):
            avail, qrRaw, qrPng = await self.localHandleAvailable(
                iphandle)
            if avail:
                await self.ipHandleLockIpfs(ipfsop, iphandle, qrRaw, qrPng)

                await self.profile.createIpIdentifier(
                    iphandle=iphandle,
                    updateProfile=True,
                    peered=True
                )

                break

        if not self.app.offline:
            await ipfsop.ctx.pubsub.services[TOPIC_PEERS].sendLogoutMessage()

        self.ui.updateButton.setEnabled(False)
        self.infoMessage('Your IP handle and DID were updated')
        self.updateProfile()

        return True

    def reject(self):
        self.done(0)
