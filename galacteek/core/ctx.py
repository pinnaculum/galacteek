import asyncio
import re
import collections
import time

from PyQt5.QtCore import (QCoreApplication, pyqtSignal, QObject)

from galacteek import log, GALACTEEK_NAME, ensure

from galacteek.ipfs import pinning
from galacteek.ipfs.wrappers import ipfsOp
from galacteek.ipfs.pubsub import *
from galacteek.ipfs.ipfsops import *
from galacteek.core.profile import UserProfile
from galacteek.core.softident import gSoftIdent
from galacteek.crypto.rsa import RSAExecutor

class PeerCtx(QObject):
    def __init__(self, ipfsCtx, peerId, identMsg, pinglast=0, pingavg=0):
        self._ipfsCtx = ipfsCtx
        self.peerId = peerId
        self.ident = identMsg
        self.pinglast = pinglast
        self.pingavg = pingavg
        self._identLast = int(time.time())

    @property
    def ipfsCtx(self):
        return self._ipfsCtx

    @property
    def ident(self):
        return self._ident

    @property
    def identLast(self):
        return self._identLast

    @property
    def peerUnresponsive(self):
        return (int(time.time()) - self.identLast) > (60*10)

    @ident.setter
    def ident(self, v):
        self._ident = v
        self._identLast = int(time.time())
        self.debug('Updated last ident to {}'.format(self.identLast))

    def debug(self, msg):
        log.debug('Peer {0}: {1}'.format(self.peerId, msg))

    @ipfsOp
    async def update(self, op):
        pass

    @ipfsOp
    async def getRsaPubKey(self, op):
        pubKeyPayload = self.ident.rsaPubKeyPem

        if pubKeyPayload:
            pubKey = await self.ipfsCtx.rsaExec.importKey(
                    pubKeyPayload)
            return pubKey
        else:
            self.debug('Failed to load pubkey')

class Peers(QObject):
    changed = pyqtSignal()
    peerAdded = pyqtSignal(str)
    peerModified = pyqtSignal(str)
    peerLogout = pyqtSignal(str)

    def __init__(self, ctx):
        super().__init__(ctx)

        self.ctx = ctx
        self.lock = asyncio.Lock()
        self.evStopWatcher = asyncio.Event()
        self._byPeerId = collections.OrderedDict()

    @property
    def byPeerId(self):
        return self._byPeerId

    @property
    def peersIds(self):
        return self.byPeerId.keys()

    @property
    def peersCount(self):
        return len(self.peersIds)

    @property
    def peersNicknames(self):
        return [peer.ident.username for pid, peer in self.byPeerId.items()]

    async def unregister(self, peerId):
        if peerId in self.byPeerId:
            del self.byPeerId[peerId]
        self.peerLogout.emit(peerId)
        self.changed.emit()

    @ipfsOp
    async def registerFromIdent(self, op, iMsg):
        # identMsg is a PeerIdentMessage

        if not iMsg.peer in self.byPeerId:
            now = int(time.time())
            avgPing = await op.waitFor(op.pingAvg(iMsg.peer, count=2), 5)

            with await self.lock:
                pCtx = PeerCtx(self.ctx, iMsg.peer, iMsg,
                    pingavg=avgPing if avgPing else 0,
                    pinglast=now if avgPing else 0
                )
                self._byPeerId[iMsg.peer] = pCtx
            self.peerAdded.emit(iMsg.peer)
        else:
            with await self.lock:
                self.peerModified.emit(iMsg.peer)
                self._byPeerId[iMsg.peer].ident = iMsg

        self.changed.emit()

    async def init(self):
        pass

    async def watch(self):
        while True:
            await asyncio.sleep(60)

            with await self.lock:
                for peerId, pCtx in self.byPeerId.items():
                    if pCtx.peerUnresponsive:
                        log.debug('{} unresponsive ..'.format(peerId))
                        await self.unregister(peerId)

    async def stop(self):
        pass

    def getByPeerId(self, peerId):
        return self._byPeerId.get(peerId, None)

    def __str__(self):
        return 'Galacteek peers registered: {0}'.format(self.peersCount)

class Node(QObject):
    def __init__(self, parent):
        super().__init__(parent)
        self.ctx = parent
        self._id = None
        self._idFull = None

    @property
    def id(self):
        return self._id

    @property
    def idAll(self):
        return self._idFull

    @ipfsOp
    async def init(self, op):
        self._idFull = await op.client.core.id()
        self._id = await op.nodeId()

class PubsubMaster(QObject):
    psMessageRx = pyqtSignal()
    psMessageTx = pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent)
        self.ctx = parent
        self._services = {}

    @property
    def services(self):
        return self._services

    def reg(self, service):
        self._services[service.topic] = service

    def status(self):
        [service.logStatus() for topic, service in self.services.items()]

    async def stop(self):
        tsks = [service.stop() for topic, service in self.services.items()]
        return await asyncio.gather(*tsks)

    def startServices(self):
        [service.start() for topic, service in self.services.items()]

    @ipfsOp
    async def init(self, op):
        pass

class P2PServices(QObject):
    def __init__(self, parent):
        super().__init__(parent)
        self.ctx = parent
        self._services = []

    @property
    def services(self):
        return self._services

    def servicesFormatted(self):
        return [ {
            'name': srv.name,
            'descr': srv.description,
            'protocol': srv.protocolName
        } for srv in self.services ]

    @ipfsOp
    async def init(self, op):
        if not await op.hasCommand('p2p') is True:
            log.debug('No P2P streams support')
            return

        log.debug('P2P streams support available')

    async def stop(self):
        for srv in self.services:
            await srv.stop()

class IPFSContext(QObject):
    # signals
    ipfsConnectionReady = pyqtSignal()
    ipfsRepositoryReady = pyqtSignal()

    # profiles
    profilesAvailable = pyqtSignal(list)
    profileChanged = pyqtSignal(str, UserProfile)
    profileInfoAvailable = pyqtSignal()

    # log events
    logAddProvider = pyqtSignal(dict)

    # pubsub
    pubsubMessageRx = pyqtSignal()
    pubsubMessageTx = pyqtSignal()

    pubsubMarksReceived = pyqtSignal(int)

    # pinning signals
    pinQueueSizeChanged = pyqtSignal(int)
    pinItemStatusChanged = pyqtSignal(str, dict)
    pinItemsCount = pyqtSignal(int)
    pinNewItem = pyqtSignal(str)
    pinFinished = pyqtSignal(str)

    def __init__(self, app):
        super().__init__()

        self._app = app

        self.objectStats = {}
        self.resources = {}
        self.profiles = {}
        self._currentProfile = None
        self.ipfsClient = None
        self._softIdent = None

        self.peers = Peers(self)
        self.node = Node(self)
        self.p2p = P2PServices(self)
        self.pubsub = PubsubMaster(self)

        self.pinner = None
        self.pinnerTask = None

    @property
    def app(self):
        return self._app

    @property
    def loop(self):
        return self.app.loop

    @property
    def client(self):
        return self.ipfsClient

    @property
    def currentProfile(self):
        return self._currentProfile

    @currentProfile.setter
    def currentProfile(self, p):
        log.debug('Switched profile: {}'.format(p.name))
        self._currentProfile = p

    @property
    def softIdent(self):
        return self._softIdent

    @softIdent.setter
    def softIdent(self, ident):
        log.debug('Software ident changed: CID {}'.format(ident['Hash']))
        self._softIdent = ident

    def hasRsc(self, name):
        return name in self.resources

    @ipfsOp
    async def setup(self, ipfsop, pubsubEnable=True,
            pubsubHashmarksExch=False, p2pEnable=False):
        self.rsaExec = RSAExecutor(loop=self.loop,
                executor=self.app.executor)
        await self.importSoftIdent()

        await self.node.init()
        await self.peers.init()

        if p2pEnable is True:
            await self.p2p.init()

        ensure(self.peers.watch())

        self.pinner = pinning.Pinner(self)
        self.pinnerTask = self.loop.create_task(self.pinner.process())

        if pubsubEnable is True:
            self.setupPubsub(pubsubHashmarksExch=pubsubHashmarksExch)

    async def shutdown(self):
        if self.pinnerTask:
            self.pinnerTask.cancel()
            await self.pinnerTask

        await self.peers.stop()
        await self.p2p.stop()
        await self.pubsub.stop()

    def setupPubsub(self, pubsubHashmarksExch=False):
        psServiceMain = PSMainService(self, self.app.ipfsClient)
        self.pubsub.reg(psServiceMain)

        psServicePeers = PSPeersService(self, self.app.ipfsClient)
        self.pubsub.reg(psServicePeers)

        if pubsubHashmarksExch:
            psServiceMarks = PSHashmarksExchanger(self, self.app.ipfsClient,
                 self.app.marksLocal, self.app.marksNetwork)
            self.pubsub.reg(psServiceMarks)

        self.pubsub.startServices()
        self.pubsub.status()

    @ipfsOp
    async def profilesInit(self, ipfsop):
        hasGalacteek = await ipfsop.filesLookup('/', GALACTEEK_NAME)
        if not hasGalacteek:
            await ipfsop.client.files.mkdir(GFILES_ROOT_PATH, parents=True)

        rootList = await ipfsop.filesList(GFILES_ROOT_PATH)

        # Scans existing profiles
        for entry in rootList:
            name = entry['Name']
            if entry['Type'] == 1 and name.startswith('profile.'):
                ma = re.search('profile\.([a-zA-Z\.\_\-]*)$', name)
                if ma:
                    profileName = ma.group(1).rstrip()
                    profile = await self.profileNew(profileName)

        defaultProfile = 'default'

        # Create default profile if not found
        if defaultProfile not in self.profiles:
            profile = await self.profileNew(defaultProfile)

        self.profileEmitAvail()
        self.profileChange(defaultProfile)

    def profileGet(self, name):
        return self.profiles.get(name, None)

    def profileEmitAvail(self):
        self.loop.call_soon(self.profilesAvailable.emit,
                list(self.profiles.keys()))

    async def profileNew(self, pName, emitavail=False):
        profile = UserProfile(self, pName,
                os.path.join(GFILES_ROOT_PATH, 'profile.{}'.format(pName)))
        try:
            await profile.init()
        except Exception as e:
            log.debug('Could not initialize profile: {}'.format(
                str(e)))
            return None
        self.profiles[pName] = profile
        if emitavail is True:
            self.profileEmitAvail()
        return profile

    def profileChange(self, pName):
        if pName in self.profiles:
            self.currentProfile = self.profiles[pName]
            self.profileChanged.emit(pName, self.currentProfile)
            return True
        else:
            return False

    @ipfsOp
    async def importSoftIdent(self, op):
        added = await op.client.add_str(gSoftIdent)
        if added is not None:
            self.softIdent = added

    @ipfsOp
    async def galacteekPeers(self, op):
        if self.softIdent is not None:
            return await op.whoProvides(self.softIdent['Hash'])
        else:
            return []