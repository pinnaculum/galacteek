import sys
import os
import os.path
import uuid
import logging
import asyncio
import jinja2
import jinja2.exceptions
import warnings
import concurrent.futures
import re
import platform
import async_timeout
import time
import aiojobs
import shutil
import signal
import psutil
from pathlib import Path
from filelock import FileLock

from distutils.version import StrictVersion

from qasync import QEventLoop

from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QDesktopWidget
from PyQt5.QtWidgets import QSystemTrayIcon
from PyQt5.QtWidgets import QMenu

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import QUrl
from PyQt5.QtCore import QStandardPaths
from PyQt5.QtCore import QTranslator
from PyQt5.QtCore import QFile
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QObject
from PyQt5.QtCore import QTemporaryDir
from PyQt5.QtCore import QDir
from PyQt5.QtCore import QMimeDatabase

from PyQt5.QtNetwork import QNetworkProxy

from PyQt5.QtGui import QCursor

from galacteek import log
from galacteek import logUser
from galacteek import ensure
from galacteek import AsyncSignal
from galacteek import pypicheck, GALACTEEK_NAME
from galacteek import asyncSigWait

from galacteek.core.fswatcher import FileWatcher

from galacteek.config import cSetSavePath
from galacteek.config import cGet
from galacteek.config import cSetDefault

from galacteek.core.asynclib import asyncify
from galacteek.core.asynclib import cancelAllTasks
from galacteek.core.asynclib import SignalNotEmittedError

from galacteek.services import cached_property
from galacteek.core.ctx import IPFSContext
from galacteek.core.profile import UserProfile
from galacteek.core.multihashmetadb import IPFSObjectMetadataDatabase
from galacteek.core.clipboard import ClipboardTracker
from galacteek.core.db import SqliteDatabase
from galacteek.core import pkgResourcesListDir
from galacteek.core import pkgResourcesRscFilename

from galacteek.browser.webproxy import NullProxy
from galacteek.browser.webproxy import useSystemProxyConfig

from galacteek import database
from galacteek.database import models

from galacteek.hashmarks import HashmarksSynchronizer

from galacteek.core.models.atomfeeds import AtomFeedsModel
from galacteek.core.signaltowers import DAGSignalsTower
from galacteek.core.signaltowers import URLSchemesTower
from galacteek.core.signaltowers import DIDTower
from galacteek.core.analyzer import ResourceAnalyzer

from galacteek.browser.schemes import SCHEME_MANUAL
from galacteek.browser.schemes import DWebSchemeHandlerGateway
from galacteek.browser.schemes import EthDNSSchemeHandler
from galacteek.browser.schemes import EthDNSProxySchemeHandler
from galacteek.browser.schemes import NativeIPFSSchemeHandler
from galacteek.browser.schemes import ObjectProxySchemeHandler
from galacteek.browser.schemes import MultiObjectHostSchemeHandler
from galacteek.browser.schemes.ipid import IPIDSchemeHandler
from galacteek.browser.schemes.ips import IPSSchemeHandler
from galacteek.browser.schemes.i import ISchemeHandler
from galacteek.browser.schemes.ipfshttp import IpfsHttpSchemeHandler
from galacteek.browser.schemes.gemini import GeminiSchemeHandler
from galacteek.browser.schemes.gemini import GemIpfsSchemeHandler
from galacteek.browser.schemes.pronto import ProntoGraphsSchemeHandler
from galacteek.browser.schemes.webtorrent import WebTorrentSchemeHandler

from galacteek.browser import BrowserRuntimeObjects
from galacteek.browser import browserSetup

from galacteek.blockchain.ethereum import ethConnConfigParams

from galacteek.space.solarsystem import SolarSystem

from galacteek.ipfs import asyncipfsd, cidhelpers
from galacteek.ipfs.cidhelpers import joinIpfs
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.wrappers import *
from galacteek.ipfs.feeds import FeedFollower
from galacteek.ipfs import distipfsfetch
from galacteek.ipfs import ipfsVersionsGenerator

from galacteek.did.ipid import IPIDManager

from galacteek.ipdapps.loader import DappsRegistry

from galacteek.ld import ldRenderersRootPath
from galacteek.ld.manager import LDSchemasImporter

from galacteek.dweb.webscripts import ipfsClientScripts
from galacteek.dweb.render import defaultJinjaEnv

from galacteek.ui import mainui
from galacteek.ui import downloads
from galacteek.ui import peers
from galacteek.ui import history
from galacteek.ui.dwebspace import *
from galacteek.ui.resource import IPFSResourceOpener
from galacteek.ui.style import GalacteekStyle
from galacteek.ui.qmlapp import qmlRegisterCustomTypes

from galacteek.ui.helpers import *
from galacteek.ui.i18n import *
from galacteek.ui.dialogs import IPFSDaemonInitDialog
from galacteek.ui.dialogs import UserProfileInitDialog
from galacteek.ui.themes import ThemesManager

from galacteek.appsettings import *
from galacteek.core.ipfsmarks import IPFSMarks

from galacteek.services.app import AppService

from yarl import URL

import aioipfs


def ipfsVersion():
    try:
        p = subprocess.Popen(['ipfs', 'version', '-n'], stdout=subprocess.PIPE)
        out, err = p.communicate()
        version = out.decode().strip()
        version = re.sub('(-.*$)', '', version)
        return StrictVersion(version)
    except BaseException:
        return None


async def fetchGoIpfsWrapper(app, timeout=60 * 10):
    try:
        await asyncio.wait_for(fetchIpfsSoft(
            app, 'kubo', 'ipfs', '0.15.0'), timeout)
    except asyncio.TimeoutError:
        app.mainWindow.statusMessage(iGoIpfsFetchTimeout())
        return None
    except Exception:
        app.mainWindow.statusMessage(iGoIpfsFetchError())
        return None
    else:
        app.mainWindow.statusMessage(iGoIpfsFetchSuccess())
        return app.which('ipfs')


async def fetchFsMigrateWrapper(app, timeout=60 * 10):
    try:
        await asyncio.wait_for(fetchIpfsSoft(
            app, 'fs-repo-migrations', 'fs-repo-migrations',
            '1.7.1'), timeout)
    except asyncio.TimeoutError:
        app.mainWindow.statusMessage(iGoIpfsFetchTimeout())
        return None
    except Exception:
        app.mainWindow.statusMessage(iGoIpfsFetchError())
        return None
    else:
        app.mainWindow.statusMessage(iGoIpfsFetchSuccess())
        return app.which('fs-repo-migrations')


async def fetchIpfsSoft(app, software, executable, version):
    async for msg in distipfsfetch.distIpfsExtract(
            dstdir=str(app.ipfsBinLocation), software=software,
            executable=executable, version=version, loop=app.loop,
            sslverify=app.sslverify):
        try:
            code, text = msg
            app.mainWindow.statusMessage(text)
        except Exception as e:
            app.debug(str(e))


class IPFSConnectionParams(object):
    def __init__(self, host, apiport, gwport):
        self._host = host
        self._apiPort = apiport
        self._gatewayPort = gwport

        self._gatewayUrl = URL.build(
            host=self.host,
            port=self.gatewayPort,
            scheme='http',
            path='')

    def asDict(self):
        return {
            'host': self.host,
            'apiPort': self.apiPort,
            'gatewayPort': self.gatewayPort,
            'gatewayUrl': self.gatewayUrl
        }

    @property
    def host(self):
        return self._host

    @property
    def apiPort(self):
        return self._apiPort

    @property
    def gatewayPort(self):
        return self._gatewayPort

    @property
    def gatewayUrl(self):
        return self._gatewayUrl


class GalacteekApplication(QApplication):
    """
    Galacteek application class

    :param bool debug: enable debugging
    :param str profile: application profile
    """

    manualAvailable = pyqtSignal(str, dict)
    messageDisplayRequest = pyqtSignal(str, str)
    appImageImported = pyqtSignal(str)

    dbConfigured = AsyncSignal(bool)

    def __init__(self, debug=False, profile='main', sslverify=True,
                 enableOrbital=False, progName=None, cmdArgs={},
                 mode='gui'):
        QApplication.__init__(self, sys.argv)

        QCoreApplication.setApplicationName(GALACTEEK_NAME)

        self.dbConfigured.connectTo(self.onDbConfigured)

        self.setQuitOnLastWindowClosed(False)

        self._mode = mode
        self._theme = None
        self._cmdArgs = cmdArgs
        self._debugEnabled = debug
        self._appProfile = profile
        self._loop = None
        self._executor = None
        self._ipfsClient = None
        self._ipfsOpMain = None
        self._ipfsd = None
        self._sslverify = sslverify
        self._progName = progName
        self._progCid = None
        self._system = platform.system()
        self._shuttingDown = False
        self._freshInstall = False
        self._process = psutil.Process(os.getpid())
        self._ldSchemasImporter = LDSchemasImporter()
        self._fsWatcherContexts = FileWatcher()
        self._fsWatcherContexts.pathChanged.connect(
            self.onLdContextsChanged)

        self._icons = {}
        self._ipfsIconsCache = {}
        self._ipfsIconsCacheMax = 32
        self._goIpfsBinPath = None

        self.sqliteDb = None
        self.scheduler = None
        self.orbitConnector = None
        self.netProxy = None

        self.translator = None
        self.mainWindow = None
        self.feedFollowerTask = None

        self.webProfiles = {}

        self.desktopWidget = QDesktopWidget()
        self.desktopGeometry = self.desktopWidget.screenGeometry()

        self.setWindowIcon(getIcon('galacteek.png'))

        self.setupAsyncLoop()
        self.setupPaths()

        self.themes = ThemesManager()
        self.ipfsCtx = IPFSContext(self)
        self.peersTracker = peers.PeersTracker(self.ipfsCtx)

    @cached_property
    def s(self) -> AppService:
        return AppService(
            dotPath='app',
            dataPath=self.dataPathForService('g'), app=self
        )

    @cached_property
    def nsCache(self) -> IPNSCache:
        return IPNSCache(self.nsCacheLocation)

    @cached_property
    def eth(self):
        return self.s.ethService

    @cached_property
    def lock(self):
        lpath = Path(self._pLockLocation)

        if not lpath.exists():
            lpath.touch()

        return FileLock(lpath, timeout=2)

    @property
    def ldSchemas(self):
        return self._ldSchemasImporter

    @property
    def theme(self):
        return self._theme

    @theme.setter
    def theme(self, theme):
        log.debug(f'Changing theme: {theme!r}')
        self._theme = theme

    @property
    def cmdArgs(self):
        return self._cmdArgs

    @property
    def shuttingDown(self):
        return self._shuttingDown

    @property
    def offline(self):
        return self.cmdArgs.offline

    @property
    def goIpfsBinPath(self):
        return self._goIpfsBinPath

    @property
    def system(self):
        return self._system

    @property
    def bsdSystem(self):
        return self.system.endswith('BSD')

    @property
    def unixSystem(self):
        return self.bsdSystem or self.linuxSystem

    @property
    def linuxSystem(self):
        return self.system == 'Linux'

    @property
    def macosSystem(self):
        return self.system == 'Darwin'

    @property
    def windowsSystem(self):
        return self.system == 'Windows'

    @property
    def debugEnabled(self):
        return self._debugEnabled

    @property
    def ipfsIconsCacheMax(self):
        return self._ipfsIconsCacheMax

    @property
    def ipfsIconsCache(self):
        return self._ipfsIconsCache

    @property
    def progName(self):
        return self._progName

    @property
    def progCid(self):
        return self._progCid

    @property
    def sslverify(self):
        return self._sslverify

    @property
    def appProfile(self):
        return self._appProfile

    @property
    def ipfsd(self):
        return self._ipfsd

    @property
    def loop(self):
        return self._loop

    @property
    def executor(self):
        return self._executor

    @loop.setter
    def loop(self, newLoop):
        self._loop = newLoop

    @property
    def py3Version(self):
        return sys.version_info.minor

    @property
    def py37(self):
        return self.py3Version == 7

    @property
    def py38(self):
        return self.py3Version == 8

    @property
    def py39(self):
        return self.py3Version == 9

    @property
    def allTasks(self):
        if self.py37 or self.py38:
            return asyncio.Task.all_tasks(loop=self.loop)
        elif self.py39:
            return asyncio.all_tasks(loop=self.loop)

    @property
    def pendingTasks(self):
        return [task for task in self.allTasks if not task.done()]

    @property
    def ipfsClient(self):
        return self._ipfsClient

    @ipfsClient.setter
    def ipfsClient(self, client):
        self.debug('IPFS client changed: {}'.format(client))
        self._ipfsClient = client

    @property
    def ipfsOpMain(self):
        return self._ipfsOpMain

    @ipfsOpMain.setter
    def ipfsOpMain(self, op):
        """ The main IPFS operator, used by @ipfsOp """
        self.debug('Main IPFS operator upgrade: ID {}'.format(op.uid))
        self._ipfsOpMain = op

    @property
    def gatewayAuthority(self):
        params = self.getIpfsConnectionParams()
        return f'{params.host}:{params.gatewayPort}'

    @property
    def gatewayUrl(self):
        params = self.getIpfsConnectionParams()
        return params.gatewayUrl

    @property
    def dataLocation(self):
        return self._dataLocation

    @property
    def ipfsBinLocation(self):
        return self._ipfsBinLocation

    @property
    def ipfsDataLocation(self):
        return self._ipfsDataLocation

    @property
    def nsCacheLocation(self):
        return self._nsCacheLocation

    @property
    def orbitDataLocation(self):
        return self._orbitDataLocation

    @property
    def cAsyncio(self):
        return cGet('asyncio')

    def readQSSFile(self, path):
        try:
            qFile = QFile(path)
            qFile.open(QFile.ReadOnly)
            styleSheetBa = qFile.readAll()
            return styleSheetBa.data().decode('utf-8')
        except BaseException as err:
            # that would probably occur if the QSS is not
            # in the resources file..  set some default stylesheet here?
            log.debug(f'readQSSFile error: {err}')

    def themeChange(self, name=None):
        theme = cGet('theme', mod='galacteek.ui')
        self.themes.change(theme)

        if self.mainWindow:
            self.repolishWidget(self.mainWindow)

    def applyStyle(self):
        self.gStyle = GalacteekStyle()
        self.setStyle(self.gStyle)

    def debug(self, msg):
        if self.debugEnabled:
            log.debug(msg)

    def networkProxy(self):
        # return QNetworkProxy.applicationProxy()
        return self.netProxy

    def networkProxySet(self, proxy):
        QNetworkProxy.setApplicationProxy(proxy)
        self.netProxy = proxy

    def networkProxySetNull(self):
        self.networkProxySet(NullProxy())

    def initSystemTray(self):
        self.systemTray = QSystemTrayIcon(self)
        self.systemTray.setIcon(getIcon('galacteek.png'))
        self.systemTray.show()
        self.systemTray.activated.connect(self.onSystemTrayIconClicked)

        systemTrayMenu = QMenu(self.mainWindow)

        actionShow = systemTrayMenu.addAction('Show')
        actionShow.setIcon(getIcon('galacteek.png'))
        actionShow.triggered.connect(self.onShowWindow)

        systemTrayMenu.addSeparator()

        actionQuit = systemTrayMenu.addAction('Quit')
        actionQuit.setIcon(getIcon('quit.png'))
        actionQuit.triggered.connect(self.onExit)

        self.systemTray.setContextMenu(systemTrayMenu)

    def initMisc(self):
        # Start with no proxy
        self.networkProxySet(NullProxy())
        useSystemProxyConfig(False)

        # Discover/preload LD schemas
        self._ldSchemasImporter.discover()

        self.multihashDb = IPFSObjectMetadataDatabase(
            str(self._mHashDbLocation), loop=self.loop)

        self.resourceOpener = IPFSResourceOpener(parent=self)

        self.downloadsManager = downloads.DownloadsManager(self)
        self.marksLocal = IPFSMarks(
            str(self.localMarksFileLocation), backup=True)

        self.marksLocal.addCategory('general')
        self.marksLocal.addCategory('uncategorized')
        self.marksNetwork = IPFSMarks(str(self.networkMarksFileLocation),
                                      autosave=False)

        self.tempDir = QTemporaryDir()
        self.tempDirWeb = self.tempDirCreate(
            self.tempDir.path(), 'webdownloads')

        self._goIpfsBinPath = self.suitableGoIpfsBinary()

        self.browserRuntime = BrowserRuntimeObjects(app=self)

        qmlRegisterCustomTypes()

    def tempDirCreate(self, basedir, name=None):
        tmpdir = QDir(basedir)

        if not tmpdir.exists():
            return

        uid = name if name else str(uuid.uuid4())

        path = tmpdir.absoluteFilePath(uid)
        if tmpdir.mkpath(path):
            return path

    async def setupHashmarks(self):
        pkg = 'galacteek.hashmarks.default'

        res = await database.hashmarkSourceSearch(
            name='core',
            url=pkg,
            type=models.HashmarkSource.TYPE_PYMODULE
        )

        if not res:
            await database.hashmarkSourceAdd(
                type=models.HashmarkSource.TYPE_PYMODULE,
                url=pkg,
                name='core'
            )
            await self.hmSynchronizer.sync()

        if 0:
            await database.hashmarkSourceAdd(
                type=models.HashmarkSource.TYPE_GITREPOS,
                url='https://gitlab.com/galacteek/hashmarks-dwebland'
            )

        await database.hashmarkSourceAdd(
            type=models.HashmarkSource.TYPE_YAML_ARCHIVE,
            url='https://gitlab.com/galacteek/hashmarks-dwebland/-/releases/continuous-master/downloads/hashmarks-dwebland.tar.gz'  # noqa
        )

        await self.scheduler.spawn(self.hmSynchronizer.syncTask())

    def setupTranslator(self):
        if self.translator:
            QApplication.removeTranslator(self.translator)

        lang = cGet('language')
        qmPath = f':/share/translations/{GALACTEEK_NAME}_{lang}.qm'

        self.translator = QTranslator()

        if self.translator.load(qmPath):
            log.debug(f'Translator load OK from: {qmPath}')
            self.installTranslator(self.translator)

    def createMainWindow(self, show=True):
        self.mainWindow = mainui.MainWindow(self)
        self.mainWindow.setupWorkspaces()

        if show is True:
            self.mainWindow.show()

    def onSystemTrayIconClicked(self, reason):
        if reason == QSystemTrayIcon.Unknown:
            pass
        elif reason == QSystemTrayIcon.Context:
            pass
        elif reason == QSystemTrayIcon.DoubleClick:
            self.mainWindow.showMaximized()
        else:
            pass

    def systemTrayMessage(self, title, message, timeout=2000,
                          messageIcon=QSystemTrayIcon.Information):
        self.systemTray.showMessage(title, message, messageIcon, timeout)

    async def startCoreServices(self):
        # By starting the top service, all subservices will be started

        try:
            async with asyncSigWait(self.s.sServiceStarted,
                                    timeout=12.0):
                await self.s.start()
        except (SignalNotEmittedError, BaseException) as sneef:
            # TODO: GUI message box
            log.warning(f'Application service could not start: {sneef}')

            self.systemTrayMessage(
                'Error starting application',
                'Error starting application',
                timeout=5000
            )

        log.debug('Application service is started now')

        await self.s.ldPublish({
            'type': 'ApplicationServiceReady'
        })

    async def importCommonResources(self):
        self.ipfsCtx.resources['ipfs-logo-ice'] = await self.importQtResource(
            '/share/icons/ipfs-logo-128-ice.png')
        self.ipfsCtx.resources['ipfs-cube-64'] = await self.importQtResource(
            '/share/icons/ipfs-cube-64.png')
        self.ipfsCtx.resources['atom-feed'] = await self.importQtResource(
            '/share/icons/atom-feed.png')
        self.ipfsCtx.resources['markdown-reference'] = \
            await self.importQtResource(
                '/share/static/docs/markdown-reference.html')

    @ipfsOp
    async def setupRepository(self, op):
        vPath = pkgResourcesRscFilename(
            'galacteek.extapps', 'video-rendezvous')
        # CHANGE
        self.ipfsCtx.resources['videocall'] = await op.addPath(vPath)

        await self.qSchemeHandler.start()

        # Trigger LD schemas update
        await self._ldSchemasImporter.update(op)

        self.feedFollower = FeedFollower(self)
        self.feedFollowerTask = await self.scheduler.spawn(
            self.feedFollower.process())

        await self.ipfsCtx.ipfsRepositoryReady.emit()
        self.ipfsCtx._ipfsRepositoryReady.emit()

        await self.s.psPublish({
            'type': 'IpfsRepositoryReady'
        })

        #
        # If the application's binary name is a valid CID, pin it!
        # This happens when running the AppImage and ensures
        # self-seeding of the image!
        #

        if isinstance(self.progName, str):
            progNameClean = re.sub(r'[\.\/]*', '', self.progName)
            if cidhelpers.cidValid(progNameClean):
                self._progCid = progNameClean
                log.debug("Auto pinning program's CID: {0}".format(
                    self.progCid))
                await self.ipfsCtx.pin(joinIpfs(self.progCid), False,
                                       self.onAppReplication,
                                       qname='self-seeding')

        if self.cmdArgs.seed and self.cmdArgs.appimage:
            await self.seedAppImage()

    @ipfsOp
    async def seedAppImage(self, ipfsop):
        # Automatic AppImage seeding

        if os.path.isfile(self.cmdArgs.binarypath):
            log.info('AppImage seeding: {img}'.format(
                img=self.cmdArgs.binarypath
            ))

            ensure(ipfsop.addPath(
                self.cmdArgs.binarypath,
                wrap=True
            ), futcallback=self.onAppSeed)

    def onAppSeed(self, future):
        try:
            replResult = future.result()
        except Exception as err:
            log.debug('AppImage seed: failed', exc_info=err)
        else:
            if isinstance(replResult, dict):
                cid = replResult.get('Hash')

                self.appImageImported.emit(cid)

                log.info('AppImage seed OK: CID {cid}'.format(
                    cid=cid))

    def onAppReplication(self, future):
        try:
            replResult = future.result()
        except Exception as err:
            log.debug('App replication: failed', exc_info=err)
        else:
            log.debug('App replication: success ({result})'.format(
                result=replResult))

    def onLdContextsChanged(self, path):
        pass

    @ipfsOp
    async def importLdRenderers(self, ipfsop):
        rdrsPath = ldRenderersRootPath()

        if not os.path.isdir(rdrsPath):
            return

        # TTL renderers
        entry = await ipfsop.addPath(
            rdrsPath, recursive=True,
            hidden=False
        )

        if entry:
            ipfsop.ctx.resources['ld-renderers'] = entry

    @ipfsOp
    async def importQtResource(self, op, path):
        rscFile = QFile(':{0}'.format(path))

        try:
            if rscFile.open(QFile.ReadOnly):
                data = rscFile.readAll().data()
                entry = await op.addBytes(data)
        except Exception as e:
            log.debug('importQtResource: {}'.format(str(e)))
        else:
            return entry

    def ipfsTask(self, fn, *args, **kw):
        """ Schedule an async IPFS task """
        return self.loop.create_task(fn(self.ipfsClient,
                                        *args, **kw))

    def ipfsTaskOp(self, fn, *args, **kw):
        """ Schedule an async IPFS task using an IPFSOperator instance """
        client = self.ipfsClient
        if client:
            return self.loop.create_task(fn(
                self.getIpfsOperator(), *args, **kw))

    def getIpfsOperator(self):
        """
        Returns a new GalacteekOperator with the currently
        active IPFS client
        """
        return self.ipfsOperatorForLoop(self.loop)

    def getIpfsConnectionParams(self):
        mgr = self.settingsMgr

        section = CFG_SECTION_IPFSD
        if mgr.isTrue(section, CFG_KEY_ENABLED):
            return IPFSConnectionParams(
                '127.0.0.1',
                mgr.getSetting(section, CFG_KEY_APIPORT),
                mgr.getSetting(section, CFG_KEY_HTTPGWPORT)
            )
        else:
            section = CFG_SECTION_IPFSCONN1
            return IPFSConnectionParams(
                mgr.getSetting(section, CFG_KEY_HOST),
                mgr.getSetting(section, CFG_KEY_APIPORT),
                mgr.getSetting(section, CFG_KEY_HTTPGWPORT)
            )

    def getEthParams(self):
        return ethConnConfigParams(self.cmdArgs.ethnet)

    def ipfsClientForLoop(self, loop):
        connParams = self.getIpfsConnectionParams()
        return aioipfs.AsyncIPFS(host=connParams.host,
                                 port=int(connParams.apiPort),
                                 loop=loop)

    def ipfsOperatorForLoop(self, loop=None):
        if not loop:
            loop = asyncio.get_running_loop()

        try:
            return getattr(loop, '_attachedIpfsOperator')
        except AttributeError:
            pass

        op = GalacteekOperator(self.ipfsClientForLoop(loop),
                               ctx=self.ipfsCtx,
                               debug=self.debugEnabled,
                               nsCache=self.nsCache)

        if self.ipfsOpMain:
            # Use crypto agents from the main operator
            if self.ipfsOpMain.rsaAgent:
                op.setRsaAgent(self.ipfsOpMain.rsaAgent)
            if self.ipfsOpMain.curve25519Agent:
                op.setCurve25519Agent(self.ipfsOpMain.curve25519Agent)

        # We share the manager but attach to the loop.. Threadsafe ? no
        # TODO: make the IPID manager thread-safe
        op.ipidManager = self.ipidManager

        # Attach
        loop._attachedIpfsOperator = op
        return op

    async def updateIpfsClient(self, client=None):
        from rdflib.plugins.sources.ipfs import ipfs_client_set_maddr

        changed = False

        if not client:
            connParams = self.getIpfsConnectionParams()
            log.debug(f'updateIpfsClient: host {connParams.host}, '
                      f'API port: {connParams.apiPort}')
            client = aioipfs.AsyncIPFS(host=connParams.host,
                                       port=int(connParams.apiPort),
                                       loop=self.loop)

        if self.ipfsClient is not client:
            changed = True

        self.ipfsClient = client
        self.ipfsCtx.ipfsClient = client

        self.ipfsOpMain = self.getIpfsOperator()
        self.ipfsOpMain.ipidManager = self.ipidManager

        IPFSOpRegistry.regDefault(self.ipfsOpMain)

        if changed:
            # rdflib client setup
            ipfs_client_set_maddr(
                f'/dns/{client.host}/tcp/{client.port}/http'
            )

            # Publish an event for services that need a notification
            # when the IPFS operator is changed

            await self.s.psPublish({
                'type': 'IpfsOperatorChange'
            })

    async def stopIpfsServices(self):
        try:
            await self.ipfsCtx.shutdown()
        except BaseException as err:
            log.debug('Error shutting down context: {err}'.format(
                err=str(err)))

        await self.ipidManager.stopManager()

        if self.feedFollowerTask is not None:
            await self.feedFollowerTask.close()

    def setupDb(self, emitConfigured=True):
        ensure(self.setupOrmDb(
            self._mainDbLocation, emitConfigured=emitConfigured))

    def jobsExceptionHandler(self, scheduler, context):
        pass

    def schedulerDumpStatus(self):
        log.debug(f'Scheduler jobs: {self.scheduler.active_count} active,'
                  f'{self.scheduler.pending_count} pending jobs')

    async def createAioScheduler(self):
        # Create the aiojobs scheduler

        cfg = self.cAsyncio.aioSchedulers.main

        self.scheduler = await aiojobs.create_scheduler(
            close_timeout=cfg.closeTimeout,
            limit=cfg.jobsLimit,
            pending_limit=cfg.pendingJobsLimit
        )

    async def setupOrmDb(self, dbpath: Path, emitConfigured=True):
        await self.createAioScheduler()

        # Old database, just for Atom feeds right now

        self.sqliteDb = SqliteDatabase(str(self._sqliteDbLocation))
        ensure(self.sqliteDb.setup())
        self.modelAtomFeeds = AtomFeedsModel(self.sqliteDb.feeds, parent=self)

        self.urlHistory = history.URLHistory(parent=self)

        if not await database.initOrm(str(dbpath)):
            await self.dbConfigured.emit(False)
            return

        await self.setupHashmarks()

        if emitConfigured:
            await self.dbConfigured.emit(True)

    async def onDbConfigured(self, configured):
        if not configured:
            return

        if self._mode != 'gui':
            return

        self.debug('Database ready')

        self.setupClipboard()
        self.setupTranslator()
        self.initSystemTray()

        await browserSetup(self, self.browserRuntime)

        self.initWebProfiles()

        self.createMainWindow()
        self.clipboardInit()
        await self.initDapps()

        await self.startCoreServices()

        await self.setupIpfsConnection()

    async def fetchGoIpfs(self):
        ipfsPath = self.which('ipfs')
        fsMigratePath = self.which('fs-repo-migrations')

        if fsMigratePath is None or self.cmdArgs.forcegoipfsdl:
            await fetchFsMigrateWrapper(self)

        if ipfsPath is None or self.cmdArgs.forcegoipfsdl:
            path = await fetchGoIpfsWrapper(self)
            if path is None:
                self.systemTrayMessage('Galacteek',
                                       iGoIpfsFetchError())

    def suitableGoIpfsBinary(self):
        if not self.windowsSystem:
            for version in ipfsVersionsGenerator():
                goIpfsBin = f'ipfs-{version}'

                if self.which(goIpfsBin):
                    log.debug(f'Found suitable kubo binary: {goIpfsBin}')
                    return goIpfsBin

        if self.which('ipfs'):
            return 'ipfs'
        else:
            log.debug('No suitable kubo binary found')

    async def setupIpfsConnection(self, reconfigure=False):
        sManager = self.settingsMgr

        if not self.goIpfsBinPath:
            await self.fetchGoIpfs()

        cfg = None
        if self._freshInstall is True or reconfigure:
            initDialog = IPFSDaemonInitDialog()
            cfg = await self.ipfsDaemonInitDialog(initDialog)
            if not cfg:
                return

        if sManager.isTrue(CFG_SECTION_IPFSD, CFG_KEY_ENABLED):
            if not self.goIpfsBinPath:
                await messageBoxAsync('kubo could not be found')
                return await self.exitApp()

            fsMigratePath = shutil.which('fs-repo-migrations')
            hasFsMigrate = fsMigratePath is not None

            if hasFsMigrate is False and self.cmdArgs.migrate is True:
                self.systemTrayMessage('Galacteek', iFsRepoMigrateNotFound())

            enableMigrate = hasFsMigrate is True and \
                self.cmdArgs.migrate is True

            await self.startIpfsDaemon(
                migrateRepo=enableMigrate,
                config=cfg
            )
        else:
            await self.updateIpfsClient()

            await self.setupProfileAndRepo()

    def setupMainObjects(self):
        self.manuals = ManualsManager(self)
        self.mimeDb = QMimeDatabase()
        self.jinjaEnv = defaultJinjaEnv()
        self.solarSystem = SolarSystem()
        self.mimeTypeIcons = preloadMimeIcons()
        self.hmSynchronizer = HashmarksSynchronizer()
        self.ipidManager = IPIDManager()

        self.towers = {
            'dags': DAGSignalsTower(self),
            'schemes': URLSchemesTower(self),
            'did': DIDTower()
        }

        self.rscAnalyzer = ResourceAnalyzer(parent=self)

        self.messageDisplayRequest.connect(
            lambda msg, title: ensure(messageBoxAsync(msg, title=title)))
        self.appImageImported.connect(
            lambda cid: ensure(messageBoxAsync(
                'AppImage was imported in IPFS!')))

    def repolishWidget(self, widget):
        self.style().unpolish(widget)
        self.style().polish(widget)

    def webClientSession(self):
        from galacteek.core.asynclib import clientSessionWithProxy
        return clientSessionWithProxy(self.netProxy.url())

    def setupAsyncLoop(self):
        """
        Install the asyncqt event loop and enable debugging
        """

        from galacteek.core.aiohttpsslerror import ignore_aiohttp_ssl_error

        loop = QEventLoop(self)
        asyncio.set_event_loop(loop)
        # logging.getLogger('asyncqt').setLevel(logging.INFO)

        if self.debugEnabled:
            logging.getLogger('asyncio').setLevel(logging.DEBUG)
            loop.set_debug(True)
            warnings.simplefilter('always', ResourceWarning)
            warnings.simplefilter('always', BytesWarning)
            warnings.simplefilter('always', ImportWarning)

        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=16)

        if not self.windowsSystem:
            loop.add_signal_handler(
                signal.SIGINT,
                functools.partial(self.signalHandler, 'SIGINT'),
            )

        # Ignore KRBS errors if running with a python version < 3.7.4
        ignore_aiohttp_ssl_error(loop)

        self.loop = loop
        return loop

    def signalHandler(self, signame):
        self.debug(f'Handling signal: {signame}')

        if signame == 'SIGINT':
            ensure(self.exitApp())

    def task(self, fn, *args, **kw):
        return self.loop.create_task(fn(*args, **kw))

    def configure(self, dbSigEmit=True, full=True):
        self.initSettings()
        self.initMisc()
        self.setupMainObjects()
        self.setupSchemeHandlers()
        self.applyStyle()
        self.themeChange()

        if full is True:
            self.setupDb(emitConfigured=dbSigEmit)

    def acquireLock(self):
        if 0:
            lpath = Path(self._pLockLocation)

            if not lpath.exists():
                lpath.touch()

            self.lock = FileLock(lpath, timeout=2)

        try:
            self.lock.acquire()
        except Exception:
            return questionBox(
                'Lock',
                'The profile lock could not be acquired '
                '(another instance could be running). Ignore ?'
            )

        return True

    def setupPaths(self):
        locr = QStandardPaths.writableLocation(QStandardPaths.DataLocation)

        if not locr:
            raise Exception('No writable data location found')

        qtDataLocation = Path(locr)

        self._dataLocation = qtDataLocation.joinpath(self._appProfile)
        self._logsLocation = self.dataLocation.joinpath('logs')
        self.mainLogFileLocation = self._logsLocation.joinpath('galacteek.log')

        self._ipfsBinLocation = qtDataLocation.joinpath('ipfs-bin')
        self._ipfsDataLocation = self.dataLocation.joinpath('ipfs')
        self._ipfsdStatusLocation = self.dataLocation.joinpath('ipfsd.status')

        self._orbitDataLocation = self.dataLocation.joinpath('orbitdb')
        self._mHashDbLocation = self.dataLocation.joinpath('mhashmetadb')
        self._sqliteDbLocation = self.dataLocation.joinpath('db.sqlite')
        self._torConfigLocation = self.dataLocation.joinpath('torrc')
        self._torDataDirLocation = self.dataLocation.joinpath('tor-data')
        self._pLockLocation = self.dataLocation.joinpath('profile.lock')
        self._mainDbLocation = self.dataLocation.joinpath('db_main.sqlite3')
        self.marksDataLocation = self.dataLocation.joinpath('marks')
        self.uiDataLocation = self.dataLocation.joinpath('ui')

        self.cryptoDataLocation = self.dataLocation.joinpath('crypto')
        self.eccDataLocation = self.cryptoDataLocation.joinpath('ecc')
        self.eccChatChannelsDataLocation = self.eccDataLocation.joinpath(
            'channels')

        self.gpgDataLocation = self.cryptoDataLocation.joinpath('gpg')
        self.localMarksFileLocation = self.marksDataLocation.joinpath(
            'ipfsmarks.local.json')
        self.networkMarksFileLocation = self.marksDataLocation.joinpath(
            'ipfsmarks.network.json')
        self.pinStatusLocation = self.dataLocation.joinpath(
            'pinstatus.json')
        self._nsCacheLocation = self.dataLocation.joinpath(
            'nscache.json')
        self._torrentStateLocation = self.dataLocation.joinpath(
            'torrent_state.pickle')
        self._bitMessageDataLocation = self.dataLocation.joinpath(
            'bitmessage')
        self.geminiHostsLocation = self.dataLocation.joinpath(
            'gemini_known_hosts')

        qtConfigLocation = Path(QStandardPaths.writableLocation(
            QStandardPaths.ConfigLocation))

        cRoot = qtConfigLocation.joinpath(
            GALACTEEK_NAME).joinpath(self._appProfile)

        self.configDirLocation = cRoot.joinpath('config-0')
        self.config2DirLocation = cRoot.joinpath('config-1')

        self.settingsFileLocation = cRoot.joinpath(
            f'{GALACTEEK_NAME}.conf')

        for dir in [self._mHashDbLocation,
                    self._logsLocation,
                    self.ipfsBinLocation,
                    self._torDataDirLocation,
                    self.marksDataLocation,
                    self.cryptoDataLocation,
                    self.eccDataLocation,
                    self.eccChatChannelsDataLocation,
                    self.gpgDataLocation,
                    self.uiDataLocation,
                    self.configDirLocation]:
            dir.mkdir(parents=True, exist_ok=True)

        self.defaultDownloadsLocation = QStandardPaths.writableLocation(
            QStandardPaths.DownloadLocation)

        self.debug('Datapath: {0}, config: {1}, configfile: {2}'.format(
            self._dataLocation,
            self.configDirLocation,
            self.settingsFileLocation))

        os.environ['PATH'] += str(self.ipfsBinLocation) + os.pathsep + \
            os.environ['PATH']

        self.setupServicesPaths()

    def dataPathForService(self, serviceName: str) -> Path:
        return self.dataLocation.joinpath('services').joinpath(
            serviceName)

    def setupServicesPaths(self):
        self._bitMessageDataLocation = self.dataPathForService(
            'bitmessage')
        self._ethDataLocation = self.dataPathForService(
            'ethereum')

    def which(self, prog='ipfs'):
        path = str(self.ipfsBinLocation) + os.pathsep + os.environ['PATH']
        result = shutil.which(prog, path=path)
        return result

    def initSettings(self):
        from galacteek.config import initFromTable
        if not os.path.isfile(self.settingsFileLocation):
            self._freshInstall = True

        self.settingsMgr = SettingsManager(path=str(self.settingsFileLocation))
        setDefaultSettings(self)
        self.settingsMgr.sync()

        if self.cmdArgs.configDefault:
            log.debug('Starting with fresh config')

            try:
                p = Path(self.configDirLocation)
                if self.config2DirLocation.exists():
                    shutil.rmtree(
                        str(self.config2DirLocation),
                        ignore_errors=True
                    )
                if p.is_dir():
                    log.debug('Moving old config')
                    p.replace(self.config2DirLocation)
            except Exception as err:
                log.debug(f'Error replacing config: {err}')

        log.debug(f'Using config from directory: {self.configDirLocation}')
        cSetSavePath(self.configDirLocation)

        # Init new config system
        initFromTable()

        cSetDefault('locations.downloadsPath',
                    self.defaultDownloadsLocation,
                    'galacteek.application')

    async def ipfsDaemonInitDialog(self, dlg):
        if self.cmdArgs.configAuto:
            dlg.setDefaultNetwork()
            return dlg.options()

        await runDialogAsync(dlg)

        if dlg.result() == dlg.EXIT_QUIT:
            await self.exitApp()
            return None

        return dlg.options()

    async def startIpfsDaemon(self, migrateRepo=False,
                              config=None,
                              failedReason=None):

        pubsubEnabled = True  # mandatory now ..
        corsEnabled = self.settingsMgr.isTrue(CFG_SECTION_IPFSD,
                                              CFG_KEY_CORS)

        sManager = self.settingsMgr
        section = CFG_SECTION_IPFSD

        # Instantiate an IPFS daemon using asyncipfsd and
        # start it in a task, monitoring the initialization process

        daemonProfiles = []
        dataStore = None

        if self.ipfsd is None:
            # TODO: FFS rewrite the constructor
            self._ipfsd = asyncipfsd.AsyncIPFSDaemon(
                self.ipfsDataLocation,
                goIpfsPath=self.goIpfsBinPath,
                statusPath=self._ipfsdStatusLocation,
                ipfsNetwork=sManager.getSetting(
                    section, CFG_KEY_IPFS_NETWORK_NAME),
                apiport=sManager.getInt(
                    section, CFG_KEY_APIPORT),
                swarmport=sManager.getInt(
                    section, CFG_KEY_SWARMPORT),
                swarmportWs=sManager.getInt(section, CFG_KEY_SWARMPORT_WS),
                swarmportQuic=sManager.getInt(section, CFG_KEY_SWARMPORT_QUIC),
                swarmProtos=sManager.swarmProtosList,
                gatewayport=sManager.getInt(section, CFG_KEY_HTTPGWPORT),
                swarmLowWater=sManager.getInt(section, CFG_KEY_SWARMLOWWATER),
                swarmHighWater=sManager.getInt(
                    section, CFG_KEY_SWARMHIGHWATER),
                storageMax=sManager.getInt(section, CFG_KEY_STORAGEMAX),
                gwWritable=sManager.isTrue(section, CFG_KEY_HTTPGWWRITABLE),
                routingMode=sManager.getSetting(
                    section, CFG_KEY_ROUTINGMODE),
                pubsubRouter=sManager.getSetting(
                    section, CFG_KEY_PUBSUB_ROUTER),
                namesysPubsub=sManager.isTrue(
                    section, CFG_KEY_NAMESYS_PUBSUB),
                pubsubSigning=sManager.isTrue(
                    section, CFG_KEY_PUBSUB_USESIGNING),
                fileStore=sManager.isTrue(section, CFG_KEY_FILESTORE),
                nice=sManager.getInt(section, CFG_KEY_NICE),
                detached=sManager.isTrue(section, CFG_KEY_IPFSD_DETACHED),
                acceleratedDht=sManager.isTrue(section,
                                               CFG_KEY_ACCELERATED_DHT_CLIENT),
                pubsubEnable=pubsubEnabled, corsEnable=corsEnabled,
                migrateRepo=migrateRepo,
                debug=self.cmdArgs.goipfsdebug,
                offline=self.cmdArgs.offline,
                profiles=daemonProfiles,
                dataStore=dataStore,
                loop=self.loop)

        initDialog = IPFSDaemonInitDialog(failedReason=failedReason,
                                          parent=self.mainWindow)

        if self._shuttingDown:
            return

        if (not self.ipfsd.repoExists() or failedReason) and config is None:
            cfg = await self.ipfsDaemonInitDialog(initDialog)
            if not cfg:
                return

            if cfg['daemonType'] == 'custom':
                await self.updateIpfsClient()

                return await self.setupProfileAndRepo()

            try:
                self.ipfsd.dataStore = cfg['dataStore']
                self.ipfsd.profiles = cfg['profiles']
                self.ipfsd.apiport = cfg['apiPort']
                self.ipfsd.swarmport = cfg['swarmPort']
                self.ipfsd.swarmportQuic = cfg['swarmPort']
                self.ipfsd.gatewayport = cfg['gatewayPort']
                self.ipfsd.detached = cfg['keepDaemonRunning']
                self.ipfsd.ipfsNetworkName = cfg.get('ipfsNetworkName', 'main')
            except Exception:
                dataStore = None
                daemonProfiles = []

        await self.scheduler.spawn(
            self.startIpfsdTask(self.ipfsd, initDialog))

    @ipfsOp
    async def setupProfileAndRepo(self, ipfsop):
        from galacteek.ipfs import ConnectionError
        try:
            if not await ipfsop.alive():
                raise ConnectionError('Node could not be contacted')

            idx, ws = self.mainWindow.stack.workspaceByName(WS_STATUS)

            await ipfsop.ctx.createRootEntry()

            await self.importCommonResources()

            await self.ipfsCtx.setup(pubsubEnable=True)

            defaultExists = await ipfsop.ctx.defaultProfileExists()

            if not defaultExists:
                while True:
                    dlg = UserProfileInitDialog(
                        automatic=self.cmdArgs.configAuto)

                    if not self.cmdArgs.configAuto:
                        await runDialogAsync(dlg)

                        if not dlg.result() == 1:
                            await messageBoxAsync(
                                'You need to create an identity')
                            continue

                    idx, pDialog = ws.pushProgress('profile')
                    pDialog.spin()
                    pDialog.log('Creating profile and DID ..')

                    try:
                        async for pct, msg in ipfsop.ctx.profileNew(
                            ipfsop,
                            UserProfile.DEFAULT_PROFILE_NAME,
                            initOptions=dlg.options()
                        ):
                            pDialog.log(msg)
                            pDialog.progress(pct)
                    except Exception as err:
                        for z in range(5):
                            pDialog.log(
                                f'Error: {err} (reconfigure in {5-z} secs')
                            await ipfsop.sleep(1)

                        raise err
                    else:
                        break

                    pDialog.stop()
            else:
                idx, pDialog = ws.pushProgress('profile')
                pDialog.spin()
                pDialog.log('Loading profile ..')

                try:
                    async for pct, msg in self.ipfsCtx.profileLoad(
                            ipfsop,
                            UserProfile.DEFAULT_PROFILE_NAME):
                        pDialog.log(msg)
                        pDialog.progress(pct)
                except Exception as err:
                    import traceback
                    traceback.print_exc()
                    pDialog.log(f'Error: {err}')
                    return

                pDialog.stop()
                pDialog.log('Ready to roll')
                pDialog.showProgress(False)

            await ipfsop.sleep(0.2)

            ws.clear('profile')

            await self.ipfsCtx.start()
            await self.setupRepository()
        except ConnectionError as err:
            await messageBoxAsync(
                f'IPFS connection error: {err}')
            await self.setupIpfsConnection(reconfigure=True)
        except RecursionError as err:
            print(str(err))
        except Exception:
            import traceback
            traceback.print_exc()
            # await self.setupIpfsConnection(reconfigure=True)
        else:
            await self.ipfsCtx.ipfsConnectionReady.emit()

    async def startIpfsdTask(self, ipfsd, initDialog):
        pDialog = initDialog.progressDialog()
        ipfsd.addMessageCallback(pDialog.log)

        idx, ws = self.mainWindow.stack.workspaceByName(WS_STATUS)
        ws.push(pDialog, 'ipfsd-start')
        pDialog.spin()

        running, client = await ipfsd.loadStatus()
        if running and client:
            log.debug('Daemon was already running')

            self.systemTrayMessage('IPFS', iIpfsDaemonResumed())

            await self.updateIpfsClient(client)
            await ipfsd.peeringConfigure()
            await self.setupProfileAndRepo()
            await self.scheduler.spawn(self.ipfsd.watchProcess())
            await self.ipfsCtx.ipfsDaemonStarted.emit()

            # XXX: emit signal indicating we're reconnecting to this daemon
            ipfsd.publishReconnectingEvent()
            return

        pDialog.log('Starting daemon ...')

        try:
            async for pct, msg in ipfsd.start():
                pDialog.log(msg)
                pDialog.progress(pct)
        except Exception as err:
            pDialog.log(f'Error starting kubo! {err}')
            self.systemTrayMessage('IPFS', iIpfsDaemonProblem())

            return await self.startIpfsDaemon(
                failedReason=iIpfsDaemonInitProblem())

        running = False

        logUser.info(iIpfsDaemonStarted())

        # Use asyncio.wait_for to wait for the proto.eventStarted
        # event to be fired.

        for attempt in range(1, 30):
            pDialog.log(iIpfsDaemonWaiting(attempt))

            with async_timeout.timeout(1):
                try:
                    await ipfsd.proto.eventStarted.wait()
                except asyncio.CancelledError:
                    continue
                except asyncio.TimeoutError:
                    # Event not set yet, wait again
                    log.debug('IPFSD: timeout occured while waiting for '
                              'daemon to start (attempt: {0})'.format(attempt))
                    continue
                else:
                    pDialog.log('IPFS daemon is ready!')

                    # Event was set, good to go
                    logUser.info(iIpfsDaemonReady())
                    running = True
                    break

        ipfsd.rmMessageCallback(pDialog.log)
        ws.clear('ipfsd-start')

        if running is True:
            await self.updateIpfsClient()
            await self.ipfsd.peeringConfigure()
            await self.ipfsd.writeStatus()
            await self.setupProfileAndRepo()
            await self.scheduler.spawn(self.ipfsd.watchProcess())
            await self.ipfsCtx.ipfsDaemonStarted.emit()
        else:
            logUser.info(iIpfsDaemonInitProblem())

            await self.startIpfsDaemon(
                failedReason=iIpfsDaemonInitProblem())

    async def rexec(self, fn, *args):
        return await self.loop.run_in_executor(
            self.executor,
            fn,
            *args
        )

    def normalCursor(self):
        cursor = QCursor(Qt.ArrowCursor)
        QApplication.setOverrideCursor(cursor)
        QApplication.changeOverrideCursor(cursor)

    def setupClipboard(self):
        self.appClipboard = self.clipboard()
        self.clipTracker = ClipboardTracker(self, self.appClipboard)

    def clipboardInit(self):
        self.clipTracker.clipboardInit()

    def setClipboardText(self, text):
        self.clipTracker.setText(text)

    def getClipboardText(self):
        return self.clipTracker.getText()

    def initWebProfiles(self):
        from galacteek.browser.webprofiles import wpRegisterFromConfig

        self.scriptsIpfs = ipfsClientScripts(self.getIpfsConnectionParams())

        # Register web profiles
        wpRegisterFromConfig(self)

    def allWebProfilesSetAttribute(self, attribute, val):
        for pName, profile in self.webProfiles.items():
            log.debug(f'Web profile {pName}: setting attr '
                      f'{attribute}:{val}')
            profile.webSettings.setAttribute(attribute, val)

    def availableWebProfilesNames(self):
        return [p.profileName for n, p in self.webProfiles.items()]

    async def initDapps(self):
        self.dappsRegistry = DappsRegistry(self.eth, parent=self)

    def setupSchemeHandlers(self):
        # TODO: register'em automatically cause it's getting heavy

        self.dwebSchemeHandler = DWebSchemeHandlerGateway(self)
        self.ensSchemeHandler = EthDNSSchemeHandler(self)
        self.ensProxySchemeHandler = EthDNSProxySchemeHandler(self)
        self.nativeIpfsSchemeHandler = NativeIPFSSchemeHandler(
            self, noMutexes=self.cmdArgs.noipfsmutexlock
        )
        self.qSchemeHandler = MultiObjectHostSchemeHandler(self)
        self.ipidSchemeHandler = IPIDSchemeHandler(self)
        self.ipsSchemeHandler = IPSSchemeHandler(self)
        self.iSchemeHandler = ISchemeHandler(self)
        self.geminiSchemeHandler = GeminiSchemeHandler(self)
        self.gemIpfsSchemeHandler = GemIpfsSchemeHandler(self)
        self.prontoGSchemeHandler = ProntoGraphsSchemeHandler(self)
        self.webTorrentSchemeHandler = WebTorrentSchemeHandler(self)
        self.ipfsHttpSchemeHandler = IpfsHttpSchemeHandler(self)

    def subUrl(self, path):
        """ Joins the gatewayUrl and path to form a new URL """
        sub = QUrl(str(self.gatewayUrl))
        sub.setPath(path)
        return sub

    def getJinjaTemplate(self, name):
        try:
            tmpl = self.jinjaEnv.get_template(name)
        except jinja2.exceptions.TemplateNotFound:
            return None
        else:
            return tmpl

    @asyncify
    async def checkReleases(self):
        self.debug('Checking for new releases')
        newR = await pypicheck.newReleaseAvailable()
        if newR:
            self.systemTrayMessage('Galacteek',
                                   iNewReleaseAvailable(), timeout=8000)

    def showTasks(self):
        for task in self.pendingTasks:
            self.debug('Pending task: {}'.format(task))

    def onShowWindow(self):
        self.mainWindow.showMaximized()

    def restart(self):
        ensure(self.restartApp())

    async def restartApp(self):
        from galacteek.guientrypoint import appStarter
        pArgs = self.arguments()

        await self.exitApp()
        time.sleep(1)
        appStarter.startProcess(pArgs)

    def onExit(self):
        if self.ipfsd and not self.settingsMgr.changed and self.ipfsd.detached:
            keepRun = True
        else:
            keepRun = False

        ensure(self.exitApp(detachIpfsd=keepRun))

    async def shutdownScheduler(self):
        # It ain't that bad. STFS with dignity

        cfg = self.cAsyncio.aioSchedulers.main.shutdown

        for stry in range(0, max(5, cfg.closeAttempts)):
            try:
                log.warning(f'Scheduler shutdown attempt: {stry}')

                with async_timeout.timeout(cfg.closeTimeout):
                    await self.scheduler.close()
            except RecursionError:
                log.warning('shutdownScheduler: recursion error')
                break
            except asyncio.TimeoutError:
                log.warning(
                    'Timeout shutting down the scheduler (not fooled)')
                continue
            except Exception as gerr:
                log.debug(f'Error shutting down the scheduler: {gerr}')
            else:
                log.debug(f'Scheduler went down (try: {stry})')
                break

    async def exitApp(self, detachIpfsd=False):
        tasksCfg = self.cAsyncio.tasks

        self._shuttingDown = True

        self.lock.release()

        # Shutdown the core service
        await self.s.stop()

        if self.mainWindow:
            self.mainWindow.stopTimers()
            await self.mainWindow.stack.shutdown()

        if 0:
            try:
                self.systemTray.hide()
            except:
                pass

        await self.stopIpfsServices()

        # Asyncio shutdown
        await self.loop.shutdown_asyncgens()

        if self.scheduler:
            await self.shutdownScheduler()

        await cancelAllTasks(timeout=tasksCfg.cancelTimeout)

        if self.ipfsClient:
            await self.ipfsClient.close()

        if self.ipfsd:
            await self.ipfsd.writeStatus()
            await self.ipfsd.daemonClient.close()

            if detachIpfsd is False:
                self.debug('Stopping IPFS daemon (not detached)')
                self.ipfsd.stop()

        try:
            if not self.sqliteDb:
                raise ValueError('sqlite database is not opened')

            with async_timeout.timeout(0.5):
                await self.sqliteDb.close()
                await database.closeOrm()
        except ValueError:
            pass
        except Exception as err:
            self.debug(f'Error while closing database: {err}')

        if self.debug:
            self.showTasks()

        self.closeAllWindows()

        self.tempDir.remove()
        self.quit()

        if self.windowsSystem:
            # temporary, need to fix #33
            self._process.kill()


class ManualsManager(QObject):
    """
    Object responsible for importing the HTML manuals in IPFS.

    Also serves as an interface to open specific pages of the manual
    from the application's code
    """

    def __init__(self, app):
        super(ManualsManager, self).__init__()

        self.app = app
        self.registry = {}
        self._schemeHandlers = []
        self.defaultManualLang = 'en'

    def getManualEntry(self, lang):
        return self.registry.get(lang, None)

    @ipfsOp
    async def importManuals(self, ipfsop, profile):
        from galacteek.docs.manual import __manual_en_version__

        documentsList = await ipfsop.filesList(profile.pathDocuments)

        try:
            listing = pkgResourcesListDir('galacteek.docs.manual', '')
            for dir in listing:
                await ipfsop.sleep()

                if dir.startswith('__'):
                    continue

                manualAlreadyImported = False
                lang = dir

                if lang == 'en':
                    manualLinkName = '{name}.manual.{lang}.{ver}'.format(
                        name=GALACTEEK_NAME, lang=lang,
                        ver=__manual_en_version__)
                else:
                    # Just english manual for now
                    continue

                for entry in documentsList:
                    if entry['Name'] == manualLinkName:
                        self.registry[lang] = entry
                        self.app.manualAvailable.emit(lang, entry)
                        manualAlreadyImported = True
                        self.installManualSchemeHandler(entry)
                        break

                if manualAlreadyImported:
                    continue

                entry = await self.importManualLang(lang)
                if entry:
                    await ipfsop.filesLink(entry, profile.pathDocuments,
                                           name=manualLinkName)
        except Exception as e:
            log.debug('Failed importing manuals: {0}'.format(str(e)))

    async def importManualLang(self, lang):
        try:
            docPath = pkgResourcesRscFilename('galacteek.docs.manual',
                                              '{0}/html'.format(lang))
            entry = await self.importDocPath(docPath, lang)
        except Exception as e:
            log.debug('Failed importing manual ({0}) {1}'.format(
                lang, str(e)))
        else:
            return entry

    @ipfsOp
    async def importDocPath(self, ipfsop, docPath, lang):
        docEntry = await ipfsop.addPath(docPath)
        if docEntry:
            await ipfsop.sleep()
            self.registry[lang] = docEntry

            self.app.manualAvailable.emit(lang, docEntry)
            self.installManualSchemeHandler(docEntry)
            return docEntry

    def installManualSchemeHandler(self, docEntry):
        """
        Install an object proxy scheme handler to be able
        to just type 'manual:/' to access the manual from
        the browser
        """

        handler = ObjectProxySchemeHandler(
            self.app, IPFSPath(docEntry['Hash']))

        for pName, profile in self.app.webProfiles.items():
            profile.installHandler(SCHEME_MANUAL, handler)

        # Need to keep a reference somewhere for Qt
        self._schemeHandlers.append(handler)

    def browseManualPage(self, pagePath, fragment=None):
        manual = self.registry.get(self.defaultManualLang)
        if not manual:
            return False

        manualPath = IPFSPath(manual['Hash'])
        if not manualPath.valid:
            return False

        ipfsPath = manualPath.child(pagePath)
        ipfsPath.fragment = fragment

        ensure(self.app.resourceOpener.open(ipfsPath))
