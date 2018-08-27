
import sys
import json
import os, os.path
import multiprocessing
import time
import asyncio
import re
import collections
import pkg_resources
import jinja2, jinja2.exceptions

from quamash import QEventLoop

from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt5.QtGui import QPixmap, QIcon, QClipboard
from PyQt5.QtCore import (QCoreApplication, QUrl, QStandardPaths,
        QSettings, QTranslator, QFile, pyqtSignal, QObject,
        QTemporaryDir, QDateTime, QMessageLogger, QMimeDatabase)

from galacteek import pypicheck
from galacteek.core.asynclib import asyncify
from galacteek.ipfs import pinning, ipfsd, asyncipfsd, cidhelpers
from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.wrappers import *
from galacteek.ipfs.pubsub import *
from galacteek.ipfs.feeds import FeedFollower

from galacteek.ui import mainui, galacteek_rc, downloads, browser, hashmarks
from galacteek.ui.helpers import *
from galacteek.ui.i18n import *

from galacteek.appsettings import *
from galacteek.core.ipfsmarks import IPFSMarks
from galacteek.core.profile import UserProfile

from yarl import URL

import aioipfs

GALACTEEK_NAME = 'galacteek'

# Application's i18n messages

# IPFS daemon messages

def iIpfsDaemonStarted():
    return QCoreApplication.translate('Galacteek', 'IPFS daemon started')

def iIpfsDaemonGwStarted():
    return QCoreApplication.translate('Galacteek',
        "IPFS daemon's gateway started")

def iIpfsDaemonReady():
    return QCoreApplication.translate('Galacteek', 'IPFS daemon is ready')

def iIpfsDaemonProblem():
    return QCoreApplication.translate('Galacteek',
        'Problem starting IPFS daemon')

def iIpfsDaemonInitProblem():
    return QCoreApplication.translate('Galacteek',
        'Problem initializing the IPFS daemon (check the ports configuration)')

def iIpfsDaemonWaiting(count):
    return QCoreApplication.translate('Galacteek',
        'IPFS daemon: waiting for connection (try {0})'.format(count))

class IPFSConnectionParams(object):
    def __init__(self, host, apiport, gwport):
        self._host = host
        self._apiPort = apiport
        self._gatewayPort = gwport

        self._gatewayUrl = URL.build(host=self.host,
            port=self.gatewayPort, scheme='http', path='')

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

class IPFSContext(QObject):
    # signals
    ipfsRepositoryReady = pyqtSignal()

    # profiles
    profilesAvailable = pyqtSignal(list)
    profileChanged = pyqtSignal(str)

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

    def __init__(self):
        super().__init__()

        self.objectStats = {}
        self.profiles = {}
        self.currentProfile = None
        self.ipfsClient = None

    @property
    def client(self):
        return self.ipfsClient

    def setIpfsClient(self, client):
        self.ipfsClient = client

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

        self.ipfsRepositoryReady.emit()

    def profileGet(self, name):
        return self.profiles.get(name, None)

    def profileEmitAvail(self):
        self.profilesAvailable.emit(list(self.profiles.keys()))

    async def profileNew(self, pName):
        profile = UserProfile(self, pName,
                os.path.join(GFILES_ROOT_PATH, 'profile.{}'.format(pName)))
        try:
            await profile.init()
        except Exception as e:
            return None
        self.profiles[pName] = profile
        self.profileEmitAvail()
        return profile

    def profileChange(self, pName):
        if pName in self.profiles:
            self.currentProfile = self.profiles[pName]
            self.profileChanged.emit(pName)
            return True
        else:
            return False

class GalacteekApplication(QApplication):
    clipboardHasIpfs = pyqtSignal(bool, str, str)
    manualAvailable = pyqtSignal(str, dict)

    def __init__(self, debug=False, profile='main'):
        QApplication.__init__(self, sys.argv)

        QCoreApplication.setApplicationName(GALACTEEK_NAME)

        self._appProfile = profile
        self._loop = None
        self._ipfsClient = None
        self._ipfsd = None

        self.translator = None
        self.logger = QMessageLogger()

        self.mainWindow = None
        self.gWindows = []

        self.pubsubListeners = []
        self.pinnerTask = None

        self.debugEnabled = debug

        self.ipfsCtx = IPFSContext()

        self.setupPaths()
        self.setupClipboard()
        self.setupSchemeHandlers()

        self.initSettings()
        self.setupTranslator()
        self.initSystemTray()
        self.initMisc()
        self.createMainWindow()

        self.setStyle()
        self.clipboardInit()

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
    def ipfsClient(self):
        return self._ipfsClient

    @property
    def gatewayAuthority(self):
        params = self.getIpfsConnectionParams()
        return '{0}:{1}'.format(params.host, params.gatewayPort)

    @property
    def gatewayUrl(self):
        params = self.getIpfsConnectionParams()
        return params.gatewayUrl

    @property
    def ipfsBinLocation(self):
        return self._ipfsBinLocation

    @property
    def ipfsDataLocation(self):
        return self._ipfsDataLocation

    def setStyle(self):
        qssPath = ":/share/static/qss/galacteek.qss"
        qssFile = QFile(qssPath)

        try:
            qssFile.open(QFile.ReadOnly)
            styleSheetBa = qssFile.readAll()
            styleSheetStr = styleSheetBa.data().decode('utf-8')
            self.setStyleSheet(styleSheetStr)
        except:
            # that would probably occur if the QSS is not in the resources file..
            # set some default stylesheet here?
            pass

    def debug(self, msg):
        if self.debugEnabled:
            self.logger.debug(msg)

    def initSystemTray(self):
        self.systemTray = QSystemTrayIcon(self)
        self.systemTray.setIcon(getIcon('ipfs-logo-128-ice-text.png'))
        self.systemTray.show()
        self.systemTray.activated.connect(self.onSystemTrayIconClicked)
        self.systemTray.setToolTip('Galacteek')

        systemTrayMenu = QMenu(None)

        action = systemTrayMenu.addAction('Quit')
        action.setIcon(QIcon.fromTheme('application-exit'))
        action.triggered.connect(self.onExit)

        self.systemTray.setContextMenu(systemTrayMenu)

    def initMisc(self):
        self.jinjaEnv = jinja2.Environment(
            loader=jinja2.PackageLoader('galacteek', 'templates'))

        self.manuals = ManualsImporter(self)
        self.mimeDb = QMimeDatabase()

        self.downloadsManager = downloads.DownloadsManager(self)
        self.marksLocal = IPFSMarks(self.localMarksFileLocation)
        self.importDefaultHashmarks(self.marksLocal)

        self.marksLocal.addCategory('general')
        self.marksNetwork = IPFSMarks(self.networkMarksFileLocation)

        self.tempDir = QTemporaryDir()
        if not self.tempDir.isValid():
            pass

    def importDefaultHashmarks(self, marksLocal):
        pkg = 'galacteek.hashmarks.default'
        try:
            listing = pkg_resources.resource_listdir(pkg, '')
            for fn in listing:
                if fn.endswith('.json'):
                    path = pkg_resources.resource_filename(pkg, fn)
                    self.debug('Importing hashmark file: {}'.format(path))
                    marks = IPFSMarks(path)
                    marksLocal.merge(marks)
        except Exception as e:
            self.debug(str(e))

    def setupTranslator(self):
        if self.translator:
            QApplication.removeTranslator(self.translator)

        self.translator = QTranslator()
        QApplication.installTranslator(self.translator)
        lang = self.settingsMgr.getSetting(CFG_SECTION_UI, CFG_KEY_LANG)
        self.translator.load(':/share/translations/galacteek_{0}.qm'.format(
            lang))

    def createMainWindow(self, show=True):
        self.mainWindow = mainui.MainWindow(self)
        if show is True:
            self.mainWindow.show()

    def onSystemTrayIconClicked(self, reason):
        if reason == QSystemTrayIcon.Unknown:
            pass
        elif reason == QSystemTrayIcon.Context:
            pass
        elif reason == QSystemTrayIcon.DoubleClick:
            self.mainWindow.show()
        else:
            pass

    def systemTrayMessage(self, title, message, timeout=2000,
            messageIcon=QSystemTrayIcon.Information):
        self.systemTray.showMessage(title, message, messageIcon, timeout)

    def setupRepository(self):
        self.task(self.ipfsCtx.profilesInit)
        self.manuals.importManualMain()

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

    def setIpfsClient(self, client):
        self._ipfsClient = client

    def getIpfsClient(self):
        return self._ipfsClient

    def getIpfsOperator(self):
        return IPFSOperator(self.ipfsClient, ctx=self.ipfsCtx,
            debug=self.debugEnabled)

    def getIpfsConnectionParams(self):
        mgr = self.settingsMgr
        section = CFG_SECTION_IPFSD
        if mgr.isTrue(section, CFG_KEY_ENABLED):
            return IPFSConnectionParams('localhost',
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

    def updateIpfsClient(self):
        connParams = self.getIpfsConnectionParams()
        client = aioipfs.AsyncIPFS(host=connParams.host,
                port=connParams.apiPort, loop=self.loop)
        self.setIpfsClient(client)
        self.ipfsCtx.setIpfsClient(client)
        self.setupRepository()
        self.setupIpfsServices()

    def setupIpfsServices(self):
        pubsubEnabled = self.settingsMgr.isTrue(CFG_SECTION_IPFS,
            CFG_KEY_PUBSUB)
        if pubsubEnabled:
            # Main pubsub topic
            self.psListenerMain = MainListener(self.ipfsClient,
                self.loop, self.ipfsCtx)
            self.psListenerMain.start()
            self.pubsubListeners.append(self.psListenerMain)

            # Pubsub marks exchanger
            self.psListenerMarks = HashmarksExchanger(self.ipfsClient,
                self.loop, self.ipfsCtx, self.marksLocal,
                self.marksNetwork)
            self.psListenerMarks.start()
            self.pubsubListeners.append(self.psListenerMarks)

        self.feedFollower = FeedFollower(self, self.marksLocal)
        self.ipfsTaskOp(self.feedFollower.process)

    def stopIpfsServices(self):
        for s in self.pubsubListeners:
            s.stop()
        if self.pinnerTask is not None:
            self.pinnerTask.cancel()

    def startPinner(self):
        self.pinner = pinning.Pinner(self)
        self.pinnerTask = self.loop.create_task(self.pinner.process())

    def setupAsyncLoop(self):
        loop = QEventLoop(self)
        asyncio.set_event_loop(loop)
        self.setLoop(loop)
        return loop

    def setLoop(self, loop):
        self._loop = loop

    def getLoop(self):
        return self._loop

    def task(self, fn, *args, **kw):
        return self.loop.create_task(fn(*args, **kw))

    def setupPaths(self):
        qtDataLocation = QStandardPaths.writableLocation(QStandardPaths.DataLocation)

        if not qtDataLocation:
            raise Exception('No writable data location found')

        self._dataLocation = os.path.join(
                qtDataLocation, self._appProfile)

        self._ipfsBinLocation = os.path.join(qtDataLocation, 'ipfs-bin')
        self._ipfsDataLocation = os.path.join(self._dataLocation, 'ipfs')
        self.marksDataLocation = os.path.join(self._dataLocation, 'marks')
        self.localMarksFileLocation = os.path.join(self.marksDataLocation,
            'ipfsmarks.local.json')
        self.networkMarksFileLocation = os.path.join(self.marksDataLocation,
            'ipfsmarks.network.json')

        qtConfigLocation = QStandardPaths.writableLocation(
                QStandardPaths.ConfigLocation)
        self.configDirLocation = os.path.join(
                qtConfigLocation, GALACTEEK_NAME, self._appProfile)
        self.settingsFileLocation = os.path.join(
                self.configDirLocation, '{}.conf'.format(GALACTEEK_NAME))

        for dir in [ self._ipfsDataLocation,
                self.ipfsBinLocation,
                self.marksDataLocation,
                self.configDirLocation ]:
            if not os.path.exists(dir):
                os.makedirs(dir)

        self.defaultDownloadsLocation = QStandardPaths.writableLocation(
            QStandardPaths.DownloadLocation)

        self.debug('Data {0}, config {1}, configfile {2}'.format(
                self._dataLocation,
                self.configDirLocation,
                self.settingsFileLocation))

        os.environ['PATH'] += os.pathsep + self.ipfsBinLocation

    def initSettings(self):
        self.settingsMgr = SettingsManager(path=self.settingsFileLocation)
        setDefaultSettings(self)
        self.settingsMgr.sync()

    def startIpfsDaemon(self, goIpfsPath='ipfs', migrateRepo=False):
        if self.ipfsd: # we only support one daemon for now
            return

        pubsubEnabled = self.settingsMgr.isTrue(CFG_SECTION_IPFS,
            CFG_KEY_PUBSUB)
        corsEnabled = self.settingsMgr.isTrue(CFG_SECTION_IPFSD,
            CFG_KEY_CORS)

        sManager = self.settingsMgr
        section = CFG_SECTION_IPFSD

        # Instantiate an IPFS daemon using asyncipfsd and
        # start it in a task, monitoring the initialization process

        self._ipfsd = asyncipfsd.AsyncIPFSDaemon(
            self.ipfsDataLocation, goIpfsPath=goIpfsPath,
            apiport=sManager.getInt(section, CFG_KEY_APIPORT),
            swarmport=sManager.getInt(section, CFG_KEY_SWARMPORT),
            gatewayport=sManager.getInt(section, CFG_KEY_HTTPGWPORT),
            swarmLowWater=sManager.getInt(section, CFG_KEY_SWARMLOWWATER),
            swarmHighWater=sManager.getInt(section, CFG_KEY_SWARMHIGHWATER),
            storageMax=sManager.getInt(section, CFG_KEY_STORAGEMAX),
            pubsubEnable=pubsubEnabled, corsEnable=corsEnabled,
            migrateRepo=migrateRepo, debug=self.debugEnabled)

        self.task(self.startIpfsdTask, self.ipfsd)

    async def startIpfsdTask(self, ipfsd):
        res = await ipfsd.start()
        self.mainWindow.statusMessage(iIpfsDaemonStarted())

        if res:
            running = False
            self.systemTrayMessage('IPFS', iIpfsDaemonStarted(),
                timeout=1000)
            for iters in range(0, 64):
                self.mainWindow.statusMessage(iIpfsDaemonWaiting(iters))
                await asyncio.sleep(0.2)
                if ipfsd.proto.daemonReady:
                    # Good to go
                    self.systemTrayMessage('IPFS',
                        iIpfsDaemonReady(), timeout=1000)
                    running = True
                    break

            if running is True:
                self.updateIpfsClient()
            else:
                self.systemTrayMessage('IPFS', iIpfsDaemonInitProblem())
        else:
            self.systemTrayMessage('IPFS', iIpfsDaemonProblem())

    def setupClipboard(self):
        self.appClipboard = self.clipboard()
        self.clipTracker = ClipboardTracker(self.appClipboard)

    def clipboardInit(self):
        self.clipTracker.clipboardInit()

    def setClipboardText(self, text):
        self.clipTracker.setText(text)

    def getClipboardText(self):
        return self.clipTracker.getText()

    def setupSchemeHandlers(self):
        self.ipfsSchemeHandler = browser.IPFSSchemeHandler(self)

    def subUrl(self, path):
        """ Joins the gatewayUrl and path to form a new URL """
        sub = QUrl(str(self.gatewayUrl))
        sub.setPath(path)
        return sub

    def getJinjaTemplate(self, name):
        try:
            tmpl = self.jinjaEnv.get_template(name)
        except jinja2.exceptions.TemplateNotFound as e:
            return None
        else:
            return tmpl

    @asyncify
    async def checkReleases(self):
        newR = await pypicheck.newReleaseAvailable()
        if newR:
            self.systemTrayMessage('Galacteek',
                iNewReleaseAvailable(), timeout=8000)

    def onExit(self):
        self.exit()

    def exit(self):
        self.stopIpfsServices()

        if self.ipfsd:
            self.ipfsd.stop()

        self.tempDir.remove()
        self.quit()
        sys.exit(0)

class ClipboardTracker(QObject):
    """
    Tracks the system's clipboard activity and emits signals
    depending on whether or not the clipboard contains an IPFS CID or path
    """
    clipboardHasIpfs = pyqtSignal(bool, str, str)
    clipboardHistoryChanged = pyqtSignal(dict)

    def __init__(self, clipboard):
        super(ClipboardTracker, self).__init__()

        self.hasIpfs = False
        self.history = {}
        self.clipboard = clipboard
        self.clipboard.changed.connect(self.onClipboardChanged)
        self.clipboardHasIpfs.connect(self.onHasIpfs)

    def onClipboardChanged(self, mode):
        text = self.clipboard.text(mode)
        self.clipboardProcess(text, clipboardMode=mode)

    def clipboardProcess(self, text, clipboardMode=None):
        """
        Process the contents of the clipboard. If it is a valid CID/path, emit a
        signal, processed by the main window for the clipboard loader button
        """
        if not text or len(text) > 1024: # that shouldn't be worth handling
            return

        text = text.strip()
        ma = cidhelpers.ipfsRegSearchPath(text)

        if ma:
            # The clipboard contains a full IPFS path
            cid = ma.group('cid')
            if not cidhelpers.cidValid(cid):
                return
            path = ma.group('fullpath')
            self.hRecord(path)
            return self.clipboardHasIpfs.emit(True, cid, path)

        ma = cidhelpers.ipnsRegSearchPath(text)
        if ma:
            # The clipboard contains a full IPNS path
            path = ma.group('fullpath')
            self.hRecord(path)
            return self.clipboardHasIpfs.emit(True, None, path)

        ma = cidhelpers.ipfsRegSearchCid(text)
        if ma:
            # The clipboard simply contains a CID
            cid = ma.group('cid')
            if not cidhelpers.cidValid(cid):
                return

            path = joinIpfs(cid)
            self.hRecord(path)
            return self.clipboardHasIpfs.emit(True, cid, path)

        # Not a CID/path
        if clipboardMode == self.clipboardPreferredMode():
            self.clipboardHasIpfs.emit(False, None, None)

    def hLookup(self, path):
        for hTs, hItem in self.history.items():
            if hItem['path'] == path:
                return hTs, hItem

    def hRecord(self, path):
        """ Records an item in the history and emits a signal """
        now = time.time()
        itLookup = self.hLookup(path)
        self.history[now] = {
            'path': path,
            'date': QDateTime.currentDateTime()
        }
        self.clipboardHistoryChanged.emit(self.getHistory())

    def getHistory(self):
        return collections.OrderedDict(sorted(self.history.items(),
            key=lambda t: t[0]))

    def clearHistory(self):
        self.history = {}
        self.clipboardHistoryChanged.emit(self.getHistory())

    def getHistoryLatest(self):
        """ Returns latest history item """
        h = self.getHistory()
        try:
            return h.popitem(last=True)[1]
        except KeyError:
            return None

    def getCurrent(self):
        """ Returns current clipboard item """
        if self.hasIpfs:
            return self.getHistoryLatest()

    def clipboardInit(self):
        """ Used to process the clipboard's content on application's init """
        text = self.getText()
        self.clipboardProcess(text)

    def clipboardPreferredMode(self):
        return QClipboard.Selection if self.clipboard.supportsSelection() \
                else QClipboard.Clipboard

    def setText(self, text):
        """ Sets the clipboard's text content """
        self.clipboard.setText(text, self.clipboardPreferredMode())

    def getText(self):
        """ Returns clipboard's text content from the preferred source """
        return self.clipboard.text(self.clipboardPreferredMode())

    def onHasIpfs(self, valid, cid, path):
        self.hasIpfs = valid

class ManualsImporter(QObject):
    """ Imports the HTML manuals in IPFS """

    def __init__(self, app):
        super(ManualsImporter, self).__init__()

        self.app = app
        self.registry = {}

    def importManualMain(self):
        try:
            listing = pkg_resources.resource_listdir('galacteek.docs.manual', '')
            for entry in listing:
                if entry.startswith('__'):
                    continue
                self.importManualLang(entry)
        except Exception as e:
            self.app.debug('Failed importing manuals {0}'.format(str(e)))

    def importManualLang(self, lang):
        try:
            docPath = pkg_resources.resource_filename('galacteek.docs.manual',
                '{0}/html'.format(lang))
            self.app.task(self.importDocPath, docPath, lang)
        except Exception as e:
            self.app.debug('Failed importing manual ({0}) {1}'.format(
                lang, str(e)))

    @ipfsOp
    async def importDocPath(self, ipfsop, docPath, lang):
        docEntry = await ipfsop.addPath(docPath)
        if docEntry:
            self.registry[lang] = docEntry
            self.app.manualAvailable.emit(lang, docEntry)
