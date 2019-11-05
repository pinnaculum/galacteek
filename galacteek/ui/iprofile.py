import random

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import QPoint
from PyQt5.QtCore import QRect
from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QToolButton
from PyQt5.QtWidgets import QToolTip

from PyQt5.QtGui import QPixmap
from PyQt5.QtGui import QImage

from galacteek import asyncify
from galacteek import ensure
from galacteek import partialEnsure
from galacteek import log
from galacteek.ipfs.wrappers import ipfsOp

from galacteek.crypto.qrcode import IPFSQrEncoder

from galacteek.ipfs.pubsub import TOPIC_PEERS
from galacteek.ipfs.pubsub.messages import PeerIpHandleChosen

from .helpers import filesSelectImages
from .helpers import getIcon
from .helpers import questionBox
from .widgets import PopupToolButton
from . import ui_profileeditdialog
from .i18n import iUnknown


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


def iProfileInfo(vPlanet, ipHandle, did):
    return QCoreApplication.translate(
        'GalacteekWindow',
        '''<p>
             <img src=':/share/icons/planets/{0}.png'
               width='32' height='32'/>
           </p>
           <p>
            IP handle: <b>{1}</b>
           </p>
           <p>
            DID: <b>{2}</b>
           </p>
        ''').format(vPlanet.lower(), ipHandle, did)


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

    async def changeProfile(self, profile):
        self.curProfile = profile
        log.debug('Changing profile to {}'.format(profile))
        self.updateToolTip(self.curProfile)

        profile.userInfo.changed.connect(self.onInfoChanged)

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

    def onInfoChanged(self):
        ensure(self.curProfile.userWebsite.updateAboutPage())
        self.updateToolTip(self.curProfile)

    def updateToolTip(self, profile):
        self.setToolTip(iProfileInfo(
            profile.userInfo.vplanet,
            profile.userInfo.iphandle,
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

        self.loadPlanets()
        self.updateProfile()

        self.ui.labelWarning.setStyleSheet(
            'QLabel { font-weight: bold; }')
        self.ui.labelWarning.linkActivated.connect(
            self.onLabelAnchorClicked
        )

        self.ui.profileDid.setText('<b>{0}</b>'.format(
            self.profile.userInfo.personDid))

        self.ui.changeIconButton.clicked.connect(self.changeIcon)
        self.ui.updateButton.clicked.connect(self.save)
        self.ui.updateButton.setEnabled(False)
        self.ui.closeButton.clicked.connect(self.close)

        self.ui.username.textEdited.connect(self.onEdited)
        self.ui.vPlanet.currentTextChanged.connect(self.onEdited)

        self.reloadIcon()

        ensure(self.loadIpHandlesContract())

    def onLabelAnchorClicked(self, url):
        self.app.mainWindow.addBrowserTab().enterUrl(QUrl(url))

    def infoMessage(self, text):
        self.ui.labelWarning.setText(text)

    def onEdited(self, text):
        if text and self.ui.username.isEnabled():
            self.ui.updateButton.setEnabled(True)

    def updateProfile(self):
        self.ui.username.setText(self.profile.userInfo.username)

        if self.profile.userInfo.vplanet:
            self.ui.vPlanet.setCurrentText(self.profile.userInfo.vplanet)

        if self.profile.userInfo.iphandle:
            self.ui.ipHandle.setText(
                '<b>{0}</b>'.format(self.profile.userInfo.iphandle))
        else:
            self.ui.ipHandle.setText(iUnknown())

        self.ui.profileDid.setText('<b>{0}</b>'.format(
            self.profile.userInfo.personDid))

    def updateAvatarCid(self):
        pass

    def reloadIcon(self):
        ensure(self.loadIcon())

    def loadPlanets(self, planetsList=None):
        planets = planetsList if planetsList else \
            self.app.solarSystem.planetsNames

        self.ui.vPlanet.clear()

        for planet in planets:
            icon = getIcon('planets/{}.png'.format(planet.lower()))
            if icon:
                self.ui.vPlanet.addItem(icon, planet)
            else:
                self.ui.vPlanet.addItem(planet)

        self.ui.vPlanet.setEnabled(False)

    @asyncify
    async def loadIcon(self):
        avatar = await self.profile.userInfo.getAvatar()

        if isinstance(avatar, bytes):
            try:
                img1 = QImage()
                img1.loadFromData(avatar)
                img = img1.scaledToWidth(256)
                self.ui.iconPixmap.setPixmap(QPixmap.fromImage(img))
            except Exception:
                pass

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
            dag.root['avatar'] = dag.mkLink(entry['Hash'])

        await op.sleep(2)
        await self.loadIcon()
        self.updateAvatarCid()

    def save(self):
        if self.profile.userInfo.iphandleValid:
            if not questionBox('Confirmation',
                               'Are you sure you want to request '
                               'a new IP handle and DID ?'
                               ):
                return

        ensure(self.saveProfile())

    @ipfsOp
    async def ipHandleLockIpfs(self, ipfsop, iphandle, qrRaw, qrPng):
        profile = ipfsop.ctx.currentProfile

        msg = PeerIpHandleChosen.make(
            ipfsop.ctx.node.id,
            iphandle,
            qrRaw['Hash'],
            qrPng['Hash'],
        )

        async with profile.userInfo as userInfo:
            userInfo.root['iphandleqr']['raw'] = userInfo.mkLink(qrRaw)
            userInfo.root['iphandleqr']['png'] = userInfo.mkLink(qrPng)

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
            return await encoder.encodeAndStore(format=format)
        except Exception:
            # TODO
            pass

    async def loadIpHandlesContract(self):
        if not await self.app.ethereum.connected():
            self.setLimitedControls()
            return

        cOperator = self.getIpHandlesOp()

        if cOperator:
            self.ui.vPlanet.setEnabled(True)
        else:
            # If we can't load the smart contract,
            # you're stuck on Magrathea

            self.setLimitedControls()

    def setLimitedControls(self):
        self.ui.labelWarning.setText(iNoSmartContract())
        self.loadPlanets(planetsList=['Magrathea'])
        self.ui.vPlanet.setEnabled(False)
        self.ui.username.setEnabled(False)
        self.ui.updateButton.setEnabled(False)

        if not self.profile.userInfo.iphandleValid:
            btn = QPushButton('Create temporary DID', self)
            btn.clicked.connect(
                partialEnsure(self.generateTemporaryDid(btn)))
            btn.setMaximumWidth(200)
            self.ui.hLayoutTmp.addWidget(btn)

    def getIpHandlesOp(self):
        return self.app.ethereum.getDefaultLoadedOperator('iphandles')

    @ipfsOp
    async def ipHandleLock(self, ipfsop, iphandle, qrRaw, qrPng):
        profile = ipfsop.ctx.currentProfile

        cOperator = self.getIpHandlesOp()

        ret = await cOperator.registerIpHandle(
            iphandle,
            self.profile.userInfo.personDid,
            ipfsop.ctx.node.id,
            qrPng['Hash']
        )

        if not ret:
            return False

        msg = PeerIpHandleChosen.make(
            ipfsop.ctx.node.id,
            iphandle,
            qrRaw['Hash'],
            qrPng['Hash'],
        )

        async with profile.userInfo as userInfo:
            userInfo.root['iphandleqr']['raw'] = userInfo.mkLink(qrRaw)
            userInfo.root['iphandleqr']['png'] = userInfo.mkLink(qrPng)

        await ipfsop.ctx.pubsub.send(TOPIC_PEERS, msg)

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
    async def ipHandleAvailableIpfs(self, ipfsop, iphandle):
        log.debug('Checking if {} is available ..'.format(iphandle))
        # entry = await ipfsop.addString(iphandle, only_hash=True)
        # entry = await self.encodeIpHandleQr(iphandle, filename=iphandle)
        rawQr = await self.encodeIpHandleQr(iphandle, filename=iphandle,
                                            format='raw')

        if not rawQr:
            return (False, None, None)

        providers = await ipfsop.whoProvides(rawQr['Hash'], timeout=10)
        log.debug('Providers: {!r}'.format(providers))

        def isOurself(providers):
            if len(providers) == 1:
                for prov in providers:
                    if prov.get('ID') == ipfsop.ctx.node.id:
                        return True
            return False

        if len(providers) == 0 or isOurself(providers):
            rawQrPng = await self.encodeIpHandleQr(
                iphandle, filename=iphandle, format='png')
            await ipfsop.addString(iphandle)
            return (True, rawQr, rawQrPng)
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

    @ipfsOp
    async def generateTemporaryDid(self, ipfsop, btn):
        btn.hide()

        username = 'dwebnoname'
        vPlanet = self.ui.vPlanet.currentText()

        self.infoMessage('Generating temporary DID ...')

        await ipfsop.ctx.pubsub.services[TOPIC_PEERS].sendLogoutMessage()
        await self.profile.createIpIdentifier(
            updateProfile=True)

        for iphandle in self.ipHandlesGen(
                vPlanet, username, onlyrand=True):
            avail, qrRaw, qrPng = await self.ipHandleAvailableIpfs(
                iphandle)
            if avail:
                await self.ipHandleLockIpfs(iphandle, qrRaw, qrPng)
                break

        async with self.profile.userInfo as dag:
            dag.root['username'] = username
            dag.root['vplanet'] = vPlanet
            dag.root['iphandle'] = iphandle

        self.ui.updateButton.setEnabled(False)
        self.infoMessage('Your IP handle and DID were updated')
        self.updateProfile()

    @ipfsOp
    async def saveProfile(self, ipfsop):
        username = self.ui.username.text().strip()
        vPlanet = self.ui.vPlanet.currentText()
        available = False

        await ipfsop.ctx.pubsub.services[TOPIC_PEERS].sendLogoutMessage()
        self.profile.userInfo.root['iphandle'] = None

        identifier = await self.profile.createIpIdentifier(
            updateProfile=True)

        log.debug('Created IPID {}'.format(identifier.did))

        if await self.app.ethereum.connected():
            for iphandle in self.ipHandlesGen(vPlanet, username):
                avail, qrRaw, qrPng = await self.ipHandleAvailable(iphandle)
                if avail:
                    await self.ipHandleLock(iphandle, qrRaw, qrPng)
                    available = True
                    break

        if not available:
            self.infoMessage('This handle is not available')
            return

        async with self.profile.userInfo as dag:
            dag.root['username'] = username
            dag.root['vplanet'] = vPlanet
            dag.root['iphandle'] = iphandle

        self.ui.updateButton.setEnabled(False)
        self.infoMessage('Your IP handle and DID were updated')
        self.updateProfile()

    def reject(self):
        self.done(0)
