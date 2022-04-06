import os
import os.path
import time
import re
import uuid
from pathlib import Path

from cachetools import cached
from cachetools import TTLCache

import aiofiles

from PyQt5.QtCore import QObject
from PyQt5.QtCore import QFile
from PyQt5.QtCore import QIODevice
from PyQt5.QtWidgets import QMenu
from PyQt5.QtWidgets import QAction

from galacteek import log
from galacteek import logUser
from galacteek import ensure
from galacteek import ensureLater
from galacteek import AsyncSignal

from galacteek.ipfs.mutable import CipheredIPFSJson
from galacteek.ipfs.wrappers import ipfsOp
from galacteek.ipfs.encrypt import IpfsRSAAgent
from galacteek.ipfs.encrypt import IpfsCurve25519Agent
from galacteek.ipfs.dag import EvolvingDAG

from galacteek.did import didIdentRe
from galacteek.did.ipid import IPIdentifier
from galacteek.did.ipid import IPService
from galacteek.did.ipid.services.videocall import VideoCallService  # noqa

from galacteek.core.iphandle import ipHandleGen
from galacteek.core.iphandle import SpaceHandle
from galacteek.core.asynclib import asyncReadFile
from galacteek.core.models.mfs import createMFSModel

from galacteek.core.userdag import UserDAG
from galacteek.core.userdag import UserWebsite
from galacteek.core.edags.chatchannels import ChannelsDAG
from galacteek.core.edags.ngraph import PeersGraphDAG

from galacteek.core.edags.seeds import SeedsEDag
from galacteek.core.edags.seeds import MegaSeedsEDag

from galacteek.core import utcDatetimeIso
from galacteek.core import readQrcTextFile
from galacteek.core.asynclib import asyncWriteFile

from galacteek.crypto.qrcode import IPFSQrEncoder

from galacteek.ipfs.paths import posixIpfsPath
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ipfs.cidhelpers import joinIpns
from galacteek.ipfs.cidhelpers import joinIpfs

from galacteek.ui.dialogs import IPIDPasswordPromptDialog
from galacteek.ui.helpers import runDialogAsync
from galacteek.ui.helpers import messageBoxAsync

from galacteek.dweb import render
from galacteek.dweb.markdown import markitdown


class CipheredHashmarks(CipheredIPFSJson):
    pass


class IPHandlesDAG(EvolvingDAG):
    async def initDag(self, ipfsop):
        return {
            'iphandles': []
        }

    async def register(self, ipHandle):
        self.root['iphandles'].append(ipHandle)
        self.changed.emit()


class UserProfileEDAG(EvolvingDAG):
    IDENTFLAG_READONLY = 1 << 1

    async def initDag(self, ipfsop):
        now = utcDatetimeIso()

        return {
            'identities': {},
            'followingGlobal': {},
            'currentIdentityUid': None,

            'datecreated': now,
            'datemodified': now
        }

    @property
    def curIdentity(self):
        if self.root['currentIdentityUid']:
            return self.root['identities'].get(
                self.root['currentIdentityUid'])

    @property
    def username(self):
        return self.identityAttr('username')

    @property
    def email(self):
        return self.identityAttr('email')

    @property
    def iphandle(self):
        return self.identityAttr('iphandle')

    @property
    def spaceHandle(self):
        return SpaceHandle(self.iphandle)

    @property
    def iphandleValid(self):
        return SpaceHandle(self.iphandle).valid

    @property
    def personDid(self):
        return self.identityAttr('personDid')

    @property
    def vplanet(self):
        return self.identityAttr('vplanet')

    @property
    def avatar(self):
        return self.identityAttr('avatar')

    def identityAttr(self, attr):
        if self.curIdentity:
            return self.curIdentity.get(attr)

    @ipfsOp
    async def identityResolve(self, ipfsop, path):
        if self.curIdentity:
            return await self.resolve(posixIpfsPath.join(
                'identities',
                self.root['currentIdentityUid'],
                path)
            )

    @ipfsOp
    async def identityDagGet(self, ipfsop, path, identityUid=None):
        return await self.get(posixIpfsPath.join(
            'identities',
            identityUid if identityUid else self.root['currentIdentityUid'],
            path)
        )

    @ipfsOp
    async def identityGetRaw(self, ipfsop, path, identityUid=None):
        return await self.cat(posixIpfsPath.join(
            'identities',
            identityUid if identityUid else self.root['currentIdentityUid'],
            path)
        )

    @ipfsOp
    async def getAvatar(self, ipfsop):
        return await self.get('avatar')

    async def follow(self, did, iphandle):
        log.debug('Following {}'.format(did))

        async with self as uInfo:
            section = uInfo.root['followingGlobal'].setdefault('main', {})
            section[did] = {
                'iphandle': iphandle
            }

    async def followingAll(self, section='main'):
        section = self['followingGlobal'].setdefault(section, {})

        for did, info in section.items():
            yield did, info

    async def identitiesIter(self):
        async with self.read() as portal:
            for uid, identity in portal.root['identities'].items():
                yield uid, identity

    async def ipHandleExists(self, iphandle):
        async for uid, identity in self.identitiesIter():
            if identity['iphandle'] == iphandle:
                return True

        return False

    @ipfsOp
    async def createIdentity(self, ipfsop, peered=False,
                             personDid=None, setAsCurrent=True,
                             iphandle=None,
                             bio=None,
                             flags=None):
        # You never know ..

        uid = str(uuid.uuid4())
        while uid in self.root['identities'].keys():
            uid = str(uuid.uuid4())

        pFlags = flags if isinstance(flags, int) else 0

        qr = await self.encodeIpHandleQr(
            iphandle, personDid
        )

        bioEntry = await ipfsop.addString(
            bio if bio else '# Bio')

        identity = {
            'email': None,
            'flags': pFlags,

            'iphandle': iphandle,
            'iphandleqr': {
                'png': self.mkLink(qr)
            },

            'vplanet': 'Earth',

            # DIDS
            'personDid': personDid,
            'following': {},

            'avatar': self.mkLink(
                await ipfsop.importQtResource(
                    '/share/icons/ipfs-cube-64.png'
                )
            ),

            'bio': self.mkLink(bioEntry),

            'crypto': {},
            'datecreated': utcDatetimeIso(),
            'datemodified': utcDatetimeIso()
        }

        async with self as dag:
            dag.root['identities'][uid] = identity

            if setAsCurrent:
                dag.root['currentIdentityUid'] = uid

        log.debug('Created identity', uid)
        return uid, dag.root['identities'][uid]

    @ipfsOp
    async def createIdentityPeered(self, ipfsop, **kw):
        return await self.createIdentity(
            peered=True,
            **kw
        )

    @ipfsOp
    async def ipIdentifier(self, ipfsop):
        if self.personDid:
            return await ipfsop.ipidManager.load(
                self.personDid,
                timeout=10,
                localIdentifier=True
            )

    @ipfsOp
    async def encodeIpHandleQr(self, ipfsop,
                               iphandle,
                               did,
                               format='png',
                               filename=None):
        encoder = IPFSQrEncoder()

        try:
            entry = await ipfsop.addString(iphandle, pin=True, only_hash=True)
            if not entry:
                return

            await ipfsop.sleep()

            encoder.add(joinIpfs(entry['Hash']))
            encoder.add(joinIpns(ipfsop.ctx.node.id))

            if didIdentRe.match(did):
                encoder.add(did)

            return await encoder.encodeAndStore(format=format)
        except Exception:
            pass


class ProfileError(Exception):
    pass


class DIDRsaKeyStore:
    def __init__(self, profile, _storeRoot: Path):
        self.__root = _storeRoot
        self.__profile = profile

    def _privateKeyPathForDid(self, did):
        match = didIdentRe.match(did)
        if not match:
            return None

        return str(self.__root.joinpath(
            'rsa_{0}_ipid_{1}_priv.key'.format(
                self.__profile, match.group('id')
            )
        ))

    @cached(TTLCache(8, 720))
    def _privateKeyForDid(self, did):
        from Cryptodome.PublicKey import RSA

        privKeyPath = self._privateKeyPathForDid(did)
        if not privKeyPath:
            return

        if os.path.isfile(privKeyPath):
            try:
                with open(privKeyPath, 'rb') as fd:
                    privKey = RSA.import_key(fd.read())
            except Exception as err:
                log.debug(f'Cannot find privkey for DID: {did}: {err}')
                return None
            else:
                return privKey


class UserProfileStatus(QObject):
    def __init__(self, parent):
        super(UserProfileStatus, self).__init__(parent)


class UserProfile(QObject):
    """
    User profile object
    """

    DEFAULT_PROFILE_NAME = 'default'

    qrImageEncoded = AsyncSignal(bool, str)
    webPageSaved = AsyncSignal(dict, str)

    identityChanged = AsyncSignal(str, str)

    def __init__(self, ctx, name, rootDir, initOptions=None):
        super(UserProfile, self).__init__()

        self._ctx = ctx
        self._name = name
        self._rootDir = rootDir
        self._initialized = False
        self._initOptions = initOptions if initOptions else {}

        self._status = 'Available'
        self._statusMessage = ''

        self.keyRoot = 'galacteek.{}.root'.format(self.name)
        self.keyRootId = None
        self.keyMainDid = self.ipIdentifierKeyName(idx=0)

        self._didKeyStore = DIDRsaKeyStore(
            self._name,
            self.ctx.app.cryptoDataLocation
        )

        self._rsaPrivKeyPath = self.ctx.app.cryptoDataLocation.joinpath(
            'rsa_{0}_priv.key'.format(
                self.name))
        self._rsaPubKeyPath = self.ctx.app.cryptoDataLocation.joinpath(
            'rsa_{0}_pub.key'.format(self.name))
        self._rsaPubKey = None

        self._filesModel = None

        self._dagUser = None

        self.userInfo = None

        self.orbitalConfigMfs = None
        self.orbitalCfgMap = None

        self.rsaAgent = None

        self.qrImageEncoded.connectTo(self.onQrImageEncoded)
        self.webPageSaved.connectTo(self.onWebPageSaved)
        self.identityChanged.connectTo(self.onIdentitySwitch)

    def debug(self, msg):
        log.debug('Profile {0}: {1}'.format(self.name, msg))

    def userLogInfo(self, msg):
        logUser.info('profile ({0}): {1}'.format(self.name, msg))

    @property
    def initialized(self):
        return self._initialized

    @property
    def initOptions(self):
        return self._initOptions

    @property
    def status(self):
        return self._status

    @property
    def statusMessage(self):
        return self._statusMessage

    @property
    def rsaExec(self):
        return self.ctx.rsaExec

    @property
    def rsaPrivKeyPath(self):
        return self._rsaPrivKeyPath

    @property
    def rsaPubKeyPath(self):
        return self._rsaPubKeyPath

    @property
    def rsaPubKey(self):
        return self._rsaPubKey

    @rsaPubKey.setter
    def rsaPubKey(self, key):
        self._rsaPubKey = key

    @property
    def dagUser(self):
        return self._dagUser  # the DAG for this user

    @property
    def dagChatChannels(self):
        return self._dagChatChannels

    @property
    def dagNetwork(self):
        return self._dagNetwork

    @property
    def root(self):
        return self._rootDir  # profile's root dir in the MFS

    @property
    def ctx(self):
        return self._ctx  # IPFS context

    @property
    def name(self):
        return self._name

    @property
    def filesModel(self):
        return self._filesModel

    @filesModel.setter
    def filesModel(self, model):
        self._filesModel = model

    @property
    def tree(self):
        # Profile's filesystem tree list
        return [
            self.pathFiles,
            self.pathHome,
            self.pathMedia,
            self.pathData,
            self.pathHMarksLibrary,
            self.pathPlaylists,
            self.pathImages,
            self.pathPictures,
            self.pathVideos,
            self.pathDocuments,
            self.pathQrCodes,
            self.pathQrCodesEncrypted,
            self.pathMusic,
            self.pathCode,
            self.pathWebPages,
            self.pathDWebApps,
            self.pathTmp,
            self.pathDownloads,
            self.pathEncryptedFiles,
            self.pathEDagsPyramids,
            self.pathEDagsSeeds
        ]

    @property
    def pathFiles(self):
        return posixIpfsPath.join(self.root, 'files')

    @property
    def pathHome(self):
        return posixIpfsPath.join(self.pathFiles, 'home')

    @property
    def pathDocuments(self):
        return posixIpfsPath.join(self.pathFiles, 'documents')

    @property
    def pathTmp(self):
        return posixIpfsPath.join(self.pathFiles, 'tmp')

    @property
    def pathEncryptedFiles(self):
        return posixIpfsPath.join(self.pathFiles, 'sencrypted')

    @property
    def pathDownloads(self):
        return posixIpfsPath.join(self.pathFiles, 'dlc')

    @property
    def pathQrCodes(self):
        return posixIpfsPath.join(self.pathMedia, 'qrcodes')

    @property
    def pathQrCodesEncrypted(self):
        return posixIpfsPath.join(self.pathQrCodes, 'encrypted')

    @property
    def pathMedia(self):
        return posixIpfsPath.join(self.pathFiles, 'multimedia')

    @property
    def pathImages(self):
        return posixIpfsPath.join(self.pathMedia, 'images')

    @property
    def pathPictures(self):
        return posixIpfsPath.join(self.pathMedia, 'pictures')

    @property
    def pathWebPages(self):
        return posixIpfsPath.join(self.pathFiles, 'webpages')

    @property
    def pathDWebApps(self):
        return posixIpfsPath.join(self.pathFiles, 'dwebapps')

    @property
    def pathVideos(self):
        return posixIpfsPath.join(self.pathMedia, 'videos')

    @property
    def pathMusic(self):
        return posixIpfsPath.join(self.pathMedia, 'music')

    @property
    def pathCode(self):
        return posixIpfsPath.join(self.pathFiles, 'code')

    @property
    def pathWebsites(self):
        return posixIpfsPath.join(self.pathFiles, 'websites')

    @property
    def pathEtc(self):
        return posixIpfsPath.join(self.root, 'etc')

    @property
    def pathData(self):
        return posixIpfsPath.join(self.root, 'data')

    @property
    def pathEDags(self):
        return posixIpfsPath.join(self.pathData, 'edags')

    @property
    def pathEDagsSeeds(self):
        return posixIpfsPath.join(self.pathEDags, 'seeds')

    @property
    def pathEDagsPyramids(self):
        return posixIpfsPath.join(self.pathEDags, 'pyramids')

    @property
    def pathHMarksLibrary(self):
        return posixIpfsPath.join(self.pathData, 'hmarks_library')

    @property
    def pathOrbital(self):
        return posixIpfsPath.join(self.pathData, 'orbital')

    @property
    def pathOrbitalConfig(self):
        return posixIpfsPath.join(self.pathOrbital, 'config')

    @property
    def pathPlaylists(self):
        return posixIpfsPath.join(self.pathData, 'playlists')

    @property
    def pathUserInfo(self):
        return posixIpfsPath.join(self.pathData, 'userinfo.json.enc')

    @property
    def pathProfileEDag(self):
        return self.edagMetadataPath('profile')

    @property
    def pathProfileEncEDag(self):
        return self.edagEncMetadataPath('profile')

    @property
    def pathUserDagMeta(self):
        return posixIpfsPath.join(self.pathData, 'dag.main')

    @property
    def pathChatChannelsDagMeta(self):
        return posixIpfsPath.join(self.pathEDags, 'chatchannels.edag')

    @property
    def pathEDagNetwork(self):
        return posixIpfsPath.join(self.pathEDags, 'network.edag')

    @property
    def pathEdagSeedsMain(self):
        return posixIpfsPath.join(self.pathEDagsSeeds, 'ipseeds_main.enc.edag')

    @property
    def pathEdagSeedsAll(self):
        return posixIpfsPath.join(
            self.pathEDagsSeeds, 'ipseeds_main_mega.enc.edag')

    def setFilesModel(self, model):
        self.filesModel = model

    async def init(self, ipfsop):
        """
        Initialize the profile's filesystem
        """

        yield 10, 'Initializing filesystem'

        await ipfsop.filesMkdir(self.root)

        for directory in self.tree:
            await ipfsop.filesMkdir(directory)

        wPath = posixIpfsPath.join(self.pathHome, 'welcome')
        welcomeEnt = await ipfsop.filesList(wPath)

        if not welcomeEnt:
            try:
                welcome = readQrcTextFile(':/share/static/misc/welcome.md')
                tmpPath = self.ctx.app.tempDir.filePath('welcome.html')

                await asyncWriteFile(
                    tmpPath, markitdown(welcome), mode='w+t')

                await ipfsop.filesLink(
                    await ipfsop.addPath(tmpPath, wrap=True),
                    self.pathHome,
                    name='welcome'
                )
            except Exception:
                pass

        self.filesModel = createMFSModel()
        self.filesModel.setupItemsFromProfile(self)

        yield 20, 'Generating IPNS keys'

        key = await ipfsop.keyFind(self.keyRoot)
        if key is not None:
            self.keyRootId = key.get('Id', None)
        else:
            self.userLogInfo('Generating main IPNS key')
            result = await ipfsop.keyGen(self.keyRoot)
            self.keyRootId = result.get('Id', None)

        self.debug('IPNS key({0}): {1}'.format(self.keyRoot, self.keyRootId))

        yield 30, 'Initializing crypto'

        if not await self.cryptoInit():
            self.userLogInfo('Error while initializing crypto')
            raise ProfileError('Crypto init failed')

        if not await ipfsop.hasDagCommand():
            self.userLogInfo('No DAG API! ..')
            raise ProfileError('No DAG API')

        yield 40, 'Initializing EDAGs ..'
        self._dagUser = UserDAG(self.pathUserDagMeta, loop=self.ctx.loop)

        self._dagChatChannels = ChannelsDAG(
            self.pathChatChannelsDagMeta, loop=self.ctx.loop)

        self._dagNetwork = PeersGraphDAG(
            self.pathEDagNetwork, loop=self.ctx.loop,
            autoUpdateDates=True
        )

        # Seeds
        self.dagSeedsMain = SeedsEDag(
            self.pathEdagSeedsMain, loop=self.ctx.loop,
            cipheredMeta=True
        )
        self.dagSeedsAll = MegaSeedsEDag(
            self.pathEdagSeedsAll, loop=self.ctx.loop,
            cipheredMeta=True
        )

        yield 50, 'Loading EDAGs ..'
        ensure(self.dagUser.load())
        await self.dagUser.loaded

        # Chat channels
        await self.dagChatChannels.load()

        # Network EDAG
        await self.dagNetwork.load()

        # Seeds EDAGs
        await self.dagSeedsMain.load()
        await self.dagSeedsAll.load()
        await self.dagSeedsAll.associate(self.dagSeedsMain)

        self.dagUser.dagCidChanged.connect(self.onDagChange)
        ensure(self.publishDag(allowOffline=True, reschedule=True))

        yield 60, 'Loading user blog ..'
        self.userWebsite = UserWebsite(
            self.dagUser,
            self,
            self.keyRootId,
            self.ctx.app.jinjaEnv,
            parent=self
        )

        await self.userWebsite.init()

        ensure(self.update())

        self._initialized = True

        yield 70, 'Importing manual ..'
        ensure(self.ctx.app.manuals.importManuals(self))

        self._initOptions = {}
        yield 100, 'Profile ready'

    @ipfsOp
    async def cryptoInit(self, op):
        if not self.rsaPrivKeyPath.is_file() and \
                not self.rsaPubKeyPath.is_file():
            self.userLogInfo('Creating RSA keypair')

            privKey, pubKey = await self.ctx.rsaExec.genKeys()
            if privKey is None or pubKey is None:
                self.debug('RSA: keygen failed')
                return False

            try:
                async with aiofiles.open(
                        str(self.rsaPrivKeyPath), 'w+b') as fd:
                    await fd.write(privKey)

                async with aiofiles.open(str(self.rsaPubKeyPath), 'w+b') as fd:
                    await fd.write(pubKey)
            except Exception as err:
                self.debug('RSA: could not save keys: {}'.format(str(err)))
                self.userLogInfo('Error while saving RSA keys!')
                return False
            else:
                os.chmod(str(self.rsaPrivKeyPath), 0o400)
                self.userLogInfo('Successfully created RSA keypair')

        if not await self.cryptoRegisterKeys():
            self.debug('RSA: failed to register keys')
            return False

        await self.cryptoCurveInit(op)

        return True

    async def cryptoCurveInit(self, ipfsop):
        privKey, pubKey = await ipfsop.ctx.curve25Exec.genKeys()

        if not privKey or not pubKey:
            raise Exception('Could not generate main curve25519 keys')

        self._c25MainPrivKey = privKey
        self._c25MainPubKey = pubKey

        ipfsop.setCurve25519Agent(
            IpfsCurve25519Agent(ipfsop.ctx.curve25Exec,
                                self._c25MainPubKey,
                                self._c25MainPrivKey
                                )
        )

    @ipfsOp
    async def cryptoRegisterKeys(self, op):
        self.userLogInfo('Registering keys')
        try:
            pubKey = await asyncReadFile(str(self.rsaPubKeyPath))
            if pubKey is None:
                self.debug('RSA: could not read public key')
                raise Exception('pubkey error')
            self.rsaPubKey = pubKey
        except Exception as e:
            self.debug('RSA: error while importing keys {}'.format(str(e)))
            return False
        else:
            self.rsaAgent = IpfsRSAAgent(self.ctx.rsaExec,
                                         self.rsaPubKey,
                                         str(self.rsaPrivKeyPath))
            op.setRsaAgent(self.rsaAgent)

            return await self.setupProfileEDag(op)

    def randomUsername(self):
        from random_username.generate import generate_username
        return generate_username()[0]

    @ipfsOp
    async def createIpIdentifierInitial(self, ipfsop):
        # Create initial IPID

        username = self.initOptions.get('username', self.randomUsername())
        vPlanet = self.initOptions.get('vPlanet', 'Earth')

        return await self.createIpIdentifier(
            iphandle=ipHandleGen(
                username,
                vPlanet,
                peerId=ipfsop.ctx.node.id
            )
        )

    async def setupProfileEDag(self, op):
        exists = await op.filesList(self.pathProfileEDag)

        if exists:
            self.userInfo = UserProfileEDAG(
                self.pathProfileEDag, dagMetaHistoryMax=32
            )
        else:
            self.userInfo = UserProfileEDAG(
                self.pathProfileEncEDag, dagMetaHistoryMax=16,
                cipheredMeta=True
            )

        await self.userInfo.load()

        if not self.userInfo.curIdentity:
            # Create initial IPID
            ipid = await self.createIpIdentifierInitial()

        if self.userInfo.curIdentity:
            # Load our IPID with low resolve timeout
            ipid = await self.ctx.app.ipidManager.load(
                self.userInfo.personDid,
                timeout=5,
                localIdentifier=True
            )

            if not ipid:
                # Could not load the current IPID ..
                # Create a new one

                ipid = await self.createIpIdentifierInitial()

        if ipid:
            if not await ipid.avatarService():
                entry = await self.ctx.app.importQtResource(
                    '/share/icons/helmet.png'
                )

                if entry:
                    path = IPFSPath(entry['Hash'])
                    await ipid.avatarSet(path)

            pwd = self.initOptions.get('ipidRsaPassphrase', None)

            # Unlock
            if not await ipid.unlock(rsaPassphrase=pwd):
                for att in range(0, 8):
                    dlg = IPIDPasswordPromptDialog()
                    await runDialogAsync(dlg)

                    if dlg.result() == 1:
                        if await ipid.unlock(rsaPassphrase=dlg.passwd()):
                            break
                        else:
                            await messageBoxAsync('Invalid password')
                    else:
                        await messageBoxAsync(
                            'Your DID\'s private key has not been unlocked.'
                            'Regenerate a DID if you cannot find your password'
                            ' as you won\'t be able to decrypt/sign messages')
                        break
        else:
            ipid = await self.createIpIdentifierInitial()

        await ipid.upgrade()

        return True

    def ipIdentifierKeyName(self, idx: int):
        return 'galacteek.{0}.dids.{1}'.format(self.name, idx)

    async def onIdentitySwitch(self, identityUid, did):
        self.debug('Identity switched to DID {}'.format(did))

        if self.userInfo.curIdentity:
            # Load our IPID with low resolve timeout
            await self.ctx.app.ipidManager.load(
                did,
                timeout=5,
                localIdentifier=True
            )

    @ipfsOp
    async def createIpIdentifier(self, ipfsop,
                                 ipnsKey=None,
                                 peered=False,
                                 iphandle=None,
                                 updateProfile=False):
        if not iphandle:
            iphandle = ipHandleGen(
                'auto',
                'Earth',
                peerId=ipfsop.ctx.node.id
            )

        try:
            keysNames = await ipfsop.keysNames()
            useKeyIdx = 0
            for key in keysNames:
                ma = re.match(
                    r'galacteek.{0}.dids.([\d]+)$'.format(self.name),
                    key
                )
                if not ma:
                    continue

                num = int(ma.group(1))
                if num > useKeyIdx:
                    useKeyIdx = num + 1

            keySize = self.initOptions.get('ipidRsaKeySize', 2048)
            passphrase = self.initOptions.get('ipidRsaPassphrase', None)

            privKey, pubKey = await self.ctx.rsaExec.genKeys(
                keysize=int(keySize),
                passphrase=passphrase
            )

            ipid = await self.ctx.app.ipidManager.create(
                ipnsKey if ipnsKey else self.ipIdentifierKeyName(useKeyIdx),
                pubKeyPem=pubKey.decode()
            )
        except Exception as e:
            self.debug(str(e))
        else:
            didPrivKeyPath = self.ctx.app.cryptoDataLocation.joinpath(
                'rsa_{0}_ipid_{1}_priv.key'.format(
                    self.name, ipid.ipnsKey))

            async with aiofiles.open(str(didPrivKeyPath), 'w+b') as fd:
                await fd.write(privKey)

            os.chmod(str(didPrivKeyPath), 0o400)

            self.userLogInfo('Generated IPID with DID: {did}'.format(
                did=ipid.did))

            if peered:
                uid, identity = await self.userInfo.createIdentityPeered(
                    iphandle=iphandle,
                    personDid=ipid.did
                )
            else:
                uid, identity = await self.userInfo.createIdentity(
                    iphandle=iphandle,
                    personDid=ipid.did,
                    setAsCurrent=True
                )

            await self.ipIdentifierInit(ipid)

            ensure(ipid.publish())

            if updateProfile is True:
                await self.identityChanged.emit(
                    self.userInfo.root['currentIdentityUid'],
                    self.userInfo.curIdentity['personDid']
                )

            if passphrase:
                await ipid.unlock(rsaPassphrase=passphrase)

            return ipid

    @ipfsOp
    async def ipIdentifierInit(self, ipfsop, ipid: IPIdentifier):
        # Register the blog as an IP service on the DID
        blogPath = IPFSPath(joinIpns(self.keyRootId)).child('blog')
        await ipid.addServiceRaw({
            'id': ipid.didUrl(path='/blog'),
            'type': IPService.SRV_TYPE_DWEBBLOG,
            'serviceEndpoint': blogPath.ipfsUrl
        }, publish=False)

        # Register the Atom feed as an IP service on the DID
        feedPath = IPFSPath(joinIpns(self.keyRootId)).child('dfeed.atom')
        await ipid.addServiceRaw({
            'id': ipid.didUrl(path='/feed'),
            'type': IPService.SRV_TYPE_ATOMFEED,
            'serviceEndpoint': feedPath.ipfsUrl,
            'description': 'Dweb Atom feed'
        }, publish=False)

        await ipid.addServiceCollection('default')

        entry = await self.ctx.app.importQtResource('/share/icons/helmet.png')

        if entry:
            defAvatar = IPFSPath(entry['Hash'])
            await ipid.avatarSet(defAvatar)

        await ipid.upgrade()

    @ipfsOp
    async def rsaEncryptSelf(self, op, data, offline=False):
        return await self.rsaAgent.storeSelf(data, offline=offline)

    @ipfsOp
    async def rsaDecryptIpfsObj(self, op, cid):
        return await self.rsaAgent.decryptIpfsObject(cid)

    async def __rsaReadPrivateKey(self):
        log.debug('RSA: reading private key')
        return await asyncReadFile(str(self.rsaPrivKeyPath))

    def onUserInfoChanged(self):
        ensure(self.update())

    @ipfsOp
    async def reconfigureOrbit(self, ipfsop):
        await ipfsop.ctx.orbitConnector.reconfigure()

    def onDagChange(self):
        ensure(self.publishDag())

    @ipfsOp
    async def publishDag(self, op, allowOffline=False, reschedule=False):
        if not self.dagUser.dagCid:
            self.debug('DAG CID not set yet ?')
            return

        self.debug('Publishing profile DAG with CID {}'.format(
            self.dagUser.dagCid))

        result = await op.publish(self.dagUser.dagCid,
                                  key=self.keyRootId,
                                  allow_offline=allowOffline,
                                  cache='always',
                                  cacheOrigin='profile',
                                  resolve=True,
                                  lifetime='48h')

        if result is None:
            self.debug('DAG publish failed')
        else:
            self.debug('DAG publish success: {}'.format(result))

        if reschedule is True:
            self.debug('Rescheduling user DAG publish')
            ensureLater(60 * 10,
                        self.publishDag, reschedule=reschedule,
                        allowOffline=allowOffline)

    async def tmplRender(self, tmpl, **kw):
        """
        Render an HTML template (jinja)
        """
        return await render.ipfsRender(self.ctx.app.jinjaEnv,
                                       tmpl,
                                       profile=self,
                                       dag=self.dagUser.dagRoot,
                                       siteIpns=self.keyRootId,
                                       **kw)

    async def tmplRenderContained(self, tmpl, **kw):
        return await render.ipfsRenderContained(self.ctx.app.jinjaEnv,
                                                tmpl,
                                                profile=self,
                                                dag=self.dagUser.dagRoot,
                                                siteIpns=self.keyRootId,
                                                **kw)

    @ipfsOp
    async def update(self, op):
        """
        Update the user's DAG
        """

        if not self.dagUser:
            return

        await self.dagUser.loaded

        if await self.userWebsite.edag.neverUpdated():
            # First build
            await self.userWebsite.update()

    @ipfsOp
    async def storeHashmarksFromJson(self, ipfsop, senderPeerId, marksJson):
        await self.sharedHManager.store(ipfsop, senderPeerId, marksJson)

    @ipfsOp
    async def storeHashmarks(self, ipfsop, senderPeerId, ipfsMarks):
        await self.sharedHManager.store(ipfsop, senderPeerId, ipfsMarks.root)

    @ipfsOp
    async def onQrImageEncoded(self, ipfsop,
                               encrypt: bool,
                               imgPath: str):
        basename = os.path.basename(imgPath)
        file = QFile(imgPath)

        if encrypt:
            if not file.open(QIODevice.ReadOnly):
                return
            data = file.readAll().data()
            entry = await self.rsaEncryptSelf(data)
        else:
            entry = await ipfsop.addPath(imgPath, offline=True)

        if entry:
            # Link it, open it
            dst = self.pathQrCodesEncrypted if encrypt is True else \
                self.pathQrCodes
            await ipfsop.filesLink(entry, dst, name=basename)
            await self.ctx.app.resourceOpener.open(entry['Hash'])

    @ipfsOp
    async def onWebPageSaved(self, ipfsop, entry, pageTitle):
        if not pageTitle:
            pageTitle = 'Unknown.{}'.format(int(time.time()))

        await ipfsop.filesLink(entry, self.pathWebPages, name=pageTitle)

    def createMfsMenu(self, title='MFS', parent=None):
        mfsMenu = QMenu(title, parent)

        for item in self.filesModel.fsCore:
            icon = item.icon()
            action = QAction(icon, item.text(), self)
            action.setData(item)
            mfsMenu.addAction(action)
            mfsMenu.addSeparator()

        return mfsMenu

    def edagMetadataPath(self, name):
        return posixIpfsPath.join(
            self.pathEDags, f'{name}.edag.json')

    def edagEncMetadataPath(self, name):
        return posixIpfsPath.join(
            self.pathEDags, f'{name}.edag.enc.json')

    def edagPyramidMetadataPath(self, name):
        return posixIpfsPath.join(
            self.pathEDagsPyramids, f'{name}.edag.json')
