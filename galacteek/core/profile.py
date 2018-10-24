
import os.path
import uuid
import pkg_resources
import base64
from datetime import datetime
from io import BytesIO

import aiofiles

from PyQt5.QtCore import (pyqtSignal, QObject)

from galacteek import log, ensure
from galacteek.ipfs.mutable import MutableIPFSJson
from galacteek.ipfs.dag import EvolvingDAG
from galacteek.ipfs.wrappers import *
from galacteek.core.asynclib import asyncify, asyncReadFile
from galacteek.web import render
from galacteek.crypto import rsa

class UserInfos(MutableIPFSJson):
    GENDER_MALE = 0
    GENDER_FEMALE = 1
    GENDER_UNSPECIFIED = -1

    def __init__(self, ipfsFilePath, **kw):
        super().__init__(ipfsFilePath)

    def initObj(self):
        uid = str(uuid.uuid4())

        return {
            'userinfo': {
                'username': uid,
                'firstname': '',
                'lastname': '',
                'altname': '',
                'gender': -1,
                'org': '',
                'email': '',
                'country': {
                    'code': '',
                    'name': '',
                },
                'city': '',
                'langs': [],
                'avatar': {
                    'cid': '',
                },
                'crypto': {
                    'rsa': {
                        'pubkeypem': None,
                    },
                    'gpg': {},
                },
                'peerid': '',
                'date': {
                    'created': datetime.now().isoformat(' ', 'seconds'),
                    'modified': datetime.now().isoformat(' ', 'seconds'),
                },
                'uid': uid,
                'locked': False,
                'schemav': 1,
            }
        }

    @property
    def uid(self):
        return self.parser.traverse('userinfo.uid')

    @property
    def peerid(self):
        return self.parser.traverse('userinfo.peerid')

    @property
    def avatarCid(self):
        return self.parser.traverse('userinfo.avatar.cid')

    @property
    def username(self):
        return self.parser.traverse('userinfo.username')

    @property
    def firstname(self):
        return self.parser.traverse('userinfo.firstname')

    @property
    def lastname(self):
        return self.parser.traverse('userinfo.lastname')

    @property
    def email(self):
        return self.parser.traverse('userinfo.email')

    @property
    def org(self):
        return self.parser.traverse('userinfo.org')

    @property
    def countryName(self):
        return self.parser.traverse('userinfo.country.name')

    @property
    def countryCode(self):
        return self.parser.traverse('userinfo.country.code')

    @property
    def locked(self):
        return self.parser.traverse('userinfo.locked')

    @property
    def schemaVersion(self):
        return self.parser.traverse('userinfo.schemav')

    @property
    def objHash(self):
        if self.curEntry:
            return self.curEntry['Hash']

    def setAvatarCid(self, cid):
        if self.locked:
            return
        self.root['userinfo']['avatar']['cid'] = cid
        self.changed.emit()

    def setCountryInfo(self, name, code):
        if self.locked:
            return
        sec = self.root['userinfo']['country']
        sec['name'] = name
        sec['code'] = code
        self.changed.emit()

    def setInfos(self, **kw):
        if self.locked:
            return
        for key, val in kw.items():
            if not key in self.root['userinfo'].keys():
                continue
            self.root['userinfo'][key] = val
        self.root['userinfo']['modified'] = datetime.now().isoformat(
            ' ', 'seconds')
        self.changed.emit()

    def setLock(self, lock=False):
        self.root['userinfo']['locked'] = lock
        self.changed.emit()

    def valid(self):
        return True

class UserDAG(EvolvingDAG):
    def initDag(self):
        return {
            'index.html': 'Blank',
            'media': {
                'images': {},
            },
            'board': {
                'messages': []
            }
        }

class UserApp(QObject):
    def __init__(self, profile):
        super(UserApp, self).__init__(profile)

        self._profile = profile
        self.cssEntry = None

    @property
    def profile(self):
        return self._profile

    @property
    def dagRoot(self):
        return self.profile.dagUser.root

    def debug(self, msg):
        return self.profile.debug(msg)

    @ipfsOp
    async def postMessage(self, op, title, msg):
        async with self.profile.dagUser as dag:
            board = dag.dagRoot['board']
            newMsg = {
                'content': msg,
                'title': title,
                'date': datetime.now().isoformat(' ', 'minutes'),
            }
            board['messages'].append(newMsg)

        await self.update()

    @ipfsOp
    async def init(self, op):
        cssPath = pkg_resources.resource_filename('galacteek.templates',
                'public/css')
        self.cssEntry = await op.addPath(cssPath, recursive=True)

    @ipfsOp
    async def update(self, op):
        homeIndex = await self.profile.tmplRender('public/userhome.html',
                boardMessages=list(reversed(
                    self.dagRoot['board']['messages'])),
                loop=self.profile.ctx.loop)

        async with self.profile.dagUser as dag:
            dag.root['index.html'] = dag.mkLink(homeIndex)
            if self.cssEntry:
                dag.root['css'] = dag.mkLink(self.cssEntry)

            if self.profile.userInfo.avatarCid != '':
                dag.root['media']['images']['avatar'] = dag.mkLink(
                        self.profile.userInfo.avatarCid)

            if self.profile.ctx.hasRsc('ipfs-cube-64'):
                dag.root['media']['images']['ipfs-cube.png'] = dag.mkLink(
                        self.profile.ctx.resources['ipfs-cube-64'])

class UserProfile(QObject):
    """ User profile object """

    P_FILES = 'files'

    def __init__(self, ctx, name, rootDir):
        super(UserProfile, self).__init__()

        self._ctx = ctx
        self._name = name
        self._rootDir = rootDir
        self.keyRoot = 'galacteek.{}.root'.format(self.name)
        self.keyRootId = None

        self._rsaPrivKeyPath = os.path.join(self.ctx.app.cryptoDataLocation,
                'rsa_{0}_priv.key'.format(self.name))
        self._rsaPubKeyPath = os.path.join(self.ctx.app.cryptoDataLocation,
                'rsa_{0}_pub.key'.format(self.name))
        self._rsaPubKey = None

        self._filesModel = None

        self._dagUser = None
        self.userInfo = UserInfos(self.pathUserInfo)
        self.rsa = self.ctx.rsaExec

    def debug(self, msg):
        log.debug('Profile {0}: {1}'.format(self.name, msg))

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
        return self._dagUser # the DAG for this user

    @property
    def root(self):
        return self._rootDir # profile's root dir in the MFS

    @property
    def ctx(self):
        return self._ctx # IPFS context

    @property
    def name(self):
        return self._name

    @property
    def filesModel(self):
        return self._filesModel

    @property
    def tree(self):
        # Profile's filesystem tree list
        return [
            self.pathFiles,
            self.pathHome,
            self.pathMedia,
            self.pathData,
            self.pathPlaylists,
            self.pathPictures,
            self.pathVideos,
            self.pathDocuments,
            self.pathMusic,
            self.pathCode,
        ]

    @property
    def pathFiles(self):
        return os.path.join(self.root, self.P_FILES)

    @property
    def pathHome(self):
        return os.path.join(self.pathFiles, 'home')

    @property
    def pathDocuments(self):
        return os.path.join(self.pathFiles, 'documents')

    @property
    def pathMedia(self):
        return os.path.join(self.pathFiles, 'multimedia')

    @property
    def pathPictures(self):
        return os.path.join(self.pathMedia, 'pictures')

    @property
    def pathVideos(self):
        return os.path.join(self.pathMedia, 'videos')

    @property
    def pathMusic(self):
        return os.path.join(self.pathMedia, 'music')

    @property
    def pathCode(self):
        return os.path.join(self.pathFiles, 'code')

    @property
    def pathWebsites(self):
        return os.path.join(self.pathFiles, 'websites')

    @property
    def pathEtc(self):
        return os.path.join(self.root, 'etc')

    @property
    def pathData(self):
        return os.path.join(self.root, 'data')

    @property
    def pathPlaylists(self):
        return os.path.join(self.pathData, 'playlists')

    @property
    def pathUserInfo(self):
        return os.path.join(self.pathData, 'userinfo.json')

    @property
    def pathUserDagMeta(self):
        return os.path.join(self.pathData, 'dag.main')

    def setFilesModel(self, model):
        self._filesModel = model

    @ipfsOp
    async def init(self, ipfsop):
        """
        Initialize the profile's filesystem
        """

        await ipfsop.filesMkdir(self.root)

        for directory in self.tree:
            await ipfsop.filesMkdir(directory)

        keysNames = await ipfsop.keysNames()

        if self.keyRoot not in keysNames:
            await ipfsop.keyGen(self.keyRoot)

        key = await ipfsop.keyFind(self.keyRoot)
        if key is not None:
            self.keyRootId = key.get('Id', None)

        self.debug('IPNS key({0}): {1}'.format(self.keyRoot, self.keyRootId))

        ensure(self.userInfo.load())
        await self.userInfo.evLoaded.wait()

        if self.userInfo.avatarCid == '' and self.ctx.hasRsc('ipfs-logo-ice'):
            self.userInfo.setAvatarCid(self.ctx.resources['ipfs-logo-ice']['Hash'])

        if self.userInfo.peerid == '':
            self.userInfo.root['userinfo']['peerid'] = self.ctx.node.id
            self.userInfo.changed.emit()

        if await ipfsop.hasDagCommand():
            self._dagUser = UserDAG(self.pathUserDagMeta, loop=self.ctx.loop)

            ensure(self.dagUser.load())
            await self.dagUser.loaded

            self.dagUser.changed.connect(self.onDagChange)

            self.app = UserApp(self)
            await self.app.init()
            ensure(self.update())
        else:
            self.debug('DAG api not available !')

        self.userInfo.changed.connect(self.onUserInfoChanged)
        ensure(self.initCrypto())

    @ipfsOp
    async def initCrypto(self, op):
        if not os.path.isfile(self.rsaPrivKeyPath) and \
            not os.path.isfile(self.rsaPubKeyPath):

            privKey, pubKey = await self.rsa.genKeys()
            if privKey is None or pubKey is None:
                self.debug('RSA: keygen failed')
                return False

            try:
                async with aiofiles.open(self.rsaPrivKeyPath, 'w+b') as fd:
                    await fd.write(privKey)

                async with aiofiles.open(self.rsaPubKeyPath, 'w+b') as fd:
                    await fd.write(pubKey)
            except Exception as err:
                self.debug('RSA: could not save keys: {}'.format(str(err)))
                return False

        try:
            pubKey = await asyncReadFile(self.rsaPubKeyPath)
            if pubKey is None:
                self.debug('RSA: could not read public key')
                raise Exception('pubkey error')
            self.rsaPubKey = pubKey
        except Exception as e:
            self.debug('RSA: error while importing {}'.format(str(e)))
        else:
            #
            # Tough decision here .. first mechanism tried for publishing the
            # peer's public key payload was to import the PEM key in the repository
            # and transmit the CID, which is neat and handy (other peers just
            # pin/fetch the key..) ATM embedding the key's payload in the
            # userinfo offers some advantages and we can always use another
            # system later on
            #
            rsaSection = self.userInfo.root['userinfo']['crypto'].setdefault(
                'rsa', {})
            rsaSection['pubkeypem'] = self.rsaPubKey.decode()
            return True

    @ipfsOp
    async def rsaEncryptSelf(self, op, data):
        try:
            data = await self.rsa.encryptData(BytesIO(data), self.rsaPubKey)
            entry = await op.client.add_bytes(data)
            if entry:
                self.debug('RSA: self-encrypt: encoded {0} bytes to {1}'.format(
                    len(data), entry['Hash']))
                return entry['Hash']
        except aioipfs.APIError as err:
            self.debug('RSA: IPFS error {}'.format(err.message))

    @ipfsOp
    async def rsaDecryptIpfsObj(self, op, cid):
        privKey = await self.__rsaReadPrivateKey()
        try:
            data = await op.client.cat(cid)
            if data is None:
                raise ValueError('RSA decrypt, IPFS object is invalid')
            decrypted = await self.rsa.decryptData(BytesIO(data), privKey)
            if decrypted:
                self.debug('RSA: decrypted {0} bytes from {1}'.format(
                    len(decrypted), cid))
                return decrypted
        except aioipfs.APIError as err:
            self.debug('RSA: IPFS error {}'.format(err.message))
        except Exception as e:
            self.debug('RSA: unknown error while decrypting {}'.format(str(e)))

    async def __rsaReadPrivateKey(self):
        log.debug('RSA: reading private key')
        return await asyncReadFile(self.rsaPrivKeyPath)

    def onUserInfoChanged(self):
        ensure(self.update())

    def onDagChange(self):
        ensure(self.publishDag())

    @ipfsOp
    async def publishDag(self, op):
        result = await op.publish(self.dagUser.dagCid, key=self.keyRoot)

        if result is None:
            self.debug('DAG publish failed: {}'.format(result))

    async def tmplRender(self, tmpl, **kw):
        """
        Render an HTML template (jinja), passing it the profile, ipfs context
        and the DAG
        """
        return await render.ipfsRender(tmpl,
                profile=self, ipfsCtx=self.ctx, dag=self.dagUser.dagRoot,
                **kw)

    @ipfsOp
    async def update(self, op):
        """
        Update the user's DAG
        """

        await self.dagUser.loaded
        await self.app.update()
