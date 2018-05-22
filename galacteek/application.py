
import sys
import json
import os, os.path
import multiprocessing
import time
import asyncio
import re
import collections
import pkg_resources

from quamash import QEventLoop

from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt5.QtGui import QPixmap, QIcon, QClipboard
from PyQt5.QtCore import (QCoreApplication, QUrl, QStandardPaths,
        QSettings, QTranslator, QFile, pyqtSignal, QObject,
        QTemporaryDir, QDateTime, QMessageLogger)

from galacteek.ipfs import pinning, ipfsd, asyncipfsd, cidhelpers
from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.wrappers import *
from galacteek.ipfs.pubsub import *
from galacteek.ipfs.feeds import FeedFollower

from galacteek.ui import mainui, galacteek_rc, downloads, browser
from galacteek.ui.helpers import *

from galacteek.appsettings import *
from galacteek.core.ipfsmarks import IPFSMarks

from yarl import URL

import aioipfs

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
        'Problem initializing the IPFS daemon, check your config')

class IPFSConnectionParams(object):
    def __init__(self, host, apiport, gwport):
        self.host = host
        self.apiport = apiport
        self.gatewayport = gwport

    def getHost(self):
        return self.host

    def getApiPort(self):
        return self.apiport

    def getGatewayPort(self):
        return self.gatewayport

    def getGatewayUrl(self):
        return URL.build(host=self.getHost(), port=self.getGatewayPort(),
                scheme='http', path='')

class IPFSContext(QObject):
    # signals
    ipfsRepositoryReady = pyqtSignal()

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

class GalacteekApplication(QApplication):
    GALACTEEK_NAME = 'galacteek'

    clipboardHasIpfs = pyqtSignal(bool, str, str)
    documentationAvailable = pyqtSignal(str, dict)

    def __init__(self, debug=False, profile='main'):
        QApplication.__init__(self, sys.argv)

        QCoreApplication.setApplicationName(self.GALACTEEK_NAME)

        self.__profile = profile
        self._loop = None
        self._client = None
        self.logger = QMessageLogger()

        self.mainWindow = None
        self.gWindows = []

        self.ipfsd = None
        self.pubsubListeners = []
        self.pinnerTask = None

        self.debugEnabled = debug

        self.ipfsCtx = IPFSContext()

        self.setupTranslator()
        self.setupPaths()
        self.setupClipboard()
        self.setupSchemeHandlers()

        self.initSettings()
        self.initSystemTray()
        self.initMisc()
        self.createMainWindow()

        self.setStyle()
        self.clipboardInit()

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

    @property
    def ipfsConnParams(self):
        return self.getIpfsConnectionParams()

    @property
    def gatewayAuthority(self):
        params = self.ipfsConnParams
        return '{0}:{1}'.format(params.getHost(), params.getGatewayPort())

    @property
    def gatewayUrl(self):
        params = self.ipfsConnParams
        return params.getGatewayUrl()

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
        from galacteek.ui.files import makeFilesModel

        self.manuals = ManualsImporter(self)

        self.downloadsManager = downloads.DownloadsManager(self)
        self.marksLocal = IPFSMarks(self.localMarksFileLocation)
        self.marksNetwork = IPFSMarks(self.networkMarksFileLocation)
        self.filesModel = None

        self.tempDir = QTemporaryDir()
        if not self.tempDir.isValid():
            pass

    def setupTranslator(self):
        self.translator = QTranslator()
        self.translator.load(':/share/translations/galacteek_en.qm')
        QApplication.installTranslator(self.translator)

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
        async def setup(oper):
            nodeId = await oper.client.id()
            rootList = await oper.filesList('/')
            hasGalacteek = await oper.filesLookup('/', self.GALACTEEK_NAME)
            if not hasGalacteek:
                await oper.client.files.mkdir(GFILES_MYFILES_PATH, parents=True)
                await oper.client.files.mkdir(GFILES_WEBSITES_PATH, parents=True)

            self.manuals.importManualMain()
            self.ipfsCtx.ipfsRepositoryReady.emit()

        self.ipfsTaskOp(setup)

    def ipfsTask(self, fn, *args, **kw):
        """ Schedule an async IPFS task """
        return self.getLoop().create_task(fn(self.getIpfsClient(),
            *args, **kw))

    def ipfsTaskOp(self, fn, *args, **kw):
        """ Schedule an async IPFS task using an IPFSOperator instance """
        client = self.getIpfsClient()
        if client:
            return self.getLoop().create_task(fn(
                self.getIpfsOperator(), *args, **kw))

    def setIpfsClient(self, client):
        self._client = client

    def getIpfsClient(self):
        return self._client

    def getIpfsOperator(self):
        return IPFSOperator(self.getIpfsClient(), ctx=self.ipfsCtx,
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
        client = aioipfs.AsyncIPFS(host=connParams.getHost(),
                port=connParams.getApiPort(), loop=self.getLoop())
        self.setIpfsClient(client)
        self.setupRepository()

        self.setupIpfsServices()

    def setupIpfsServices(self):
        pubsubEnabled = self.settingsMgr.isTrue(CFG_SECTION_IPFS,
            CFG_KEY_PUBSUB)
        if pubsubEnabled:
            # Main pubsub topic
            listenerMain = PubsubListener(self.getIpfsClient(),
                self.getLoop(), self.ipfsCtx, topic='galacteek.main')
            listenerMain.start()
            self.pubsubListeners.append(listenerMain)

            # Pubsub marks exchanger
            listenerMarks = BookmarksExchanger(self.getIpfsClient(),
                self.getLoop(), self.ipfsCtx, self.marksLocal,
                self.marksNetwork)
            listenerMarks.start()
            self.pubsubListeners.append(listenerMarks)

        self.feedFollower = FeedFollower(self.marksLocal)
        self.ipfsTaskOp(self.feedFollower.process)

    def stopIpfsServices(self):
        for s in self.pubsubListeners:
            s.stop()
        if self.pinnerTask:
            self.pinnerTask.cancel()

    def startPinner(self):
        self.pinner = pinning.Pinner(self, self.getLoop())
        self.pinnerTask = self.getLoop().create_task(self.pinner.process())

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
        return self.getLoop().create_task(fn(*args, **kw))

    def setupPaths(self):
        qtDataLocation = QStandardPaths.writableLocation(QStandardPaths.DataLocation)
        self.dataLocation = os.path.join(
                qtDataLocation, self.__profile)

        if not self.dataLocation:
            raise Exception('No writable data location found')

        self.ipfsDataLocation = os.path.join(self.dataLocation, 'ipfs')
        self.marksDataLocation = os.path.join(self.dataLocation, 'marks')
        self.localMarksFileLocation = os.path.join(self.marksDataLocation,
            'ipfsmarks.local.json')
        self.networkMarksFileLocation = os.path.join(self.marksDataLocation,
            'ipfsmarks.network.json')

        qtConfigLocation = QStandardPaths.writableLocation(
                QStandardPaths.ConfigLocation)
        self.configDirLocation = os.path.join(
                qtConfigLocation, self.GALACTEEK_NAME, self.__profile)
        self.settingsFileLocation = os.path.join(
                self.configDirLocation, '{}.conf'.format(self.GALACTEEK_NAME))

        for dir in [ self.ipfsDataLocation,
                self.marksDataLocation,
                self.configDirLocation ]:
            if not os.path.exists(dir):
                os.makedirs(dir)

        self.defaultDownloadsLocation = QStandardPaths.writableLocation(
            QStandardPaths.DownloadLocation)

        self.debug('Data {0}, config {1}, configfile {2}'.format(
                self.dataLocation,
                self.configDirLocation,
                self.settingsFileLocation))

    def initSettings(self):
        self.settingsMgr = SettingsManager(path=self.settingsFileLocation)
        setDefaultSettings(self)
        self.settingsMgr.sync()

    def getDataLocation(self):
        return self.dataLocation

    def getIpfsDataLocation(self):
        return self.ipfsDataLocation

    def startIpfsDaemon(self):
        if self.ipfsd: # we only support one daemon for now
            return

        pubsubEnabled = self.settingsMgr.isTrue(CFG_SECTION_IPFS,
            CFG_KEY_PUBSUB)

        sManager = self.settingsMgr
        section = CFG_SECTION_IPFSD

        # Instantiate an IPFS daemon using asyncipfsd and
        # start it in a task, monitoring the initialization process

        self.ipfsd = asyncipfsd.AsyncIPFSDaemon(self.getIpfsDataLocation(),
            apiport=sManager.getInt(section, CFG_KEY_APIPORT),
            swarmport=sManager.getInt(section, CFG_KEY_SWARMPORT),
            gatewayport=sManager.getInt(section, CFG_KEY_HTTPGWPORT),
            swarmLowWater=sManager.getInt(section, CFG_KEY_SWARMLOWWATER),
            swarmHighWater=sManager.getInt(section, CFG_KEY_SWARMHIGHWATER),
            pubsubEnable=pubsubEnabled)

        self.task(self.startIpfsdTask, self.ipfsd)
        return self.ipfsd

    async def startIpfsdTask(self, ipfsd):
        res = await ipfsd.start()

        if res:
            running = False
            self.systemTrayMessage('IPFS', iIpfsDaemonStarted(),
                timeout=1000)
            for iters in range(0, 64):
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

    def onExit(self):
        self.stopIpfsServices()

        if self.ipfsd:
            self.ipfsd.stop()

        self.tempDir.remove()
        self.quit()
        sys.exit(1)

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
        self.clipboardProcess(text)

    def clipboardProcess(self, text):
        """
        Process the contents of the clipboard. If it is a valid CID, emit a
        signal, processed by the main window for the clipboard loader button
        """
        if not text or len(text) > 1024: # that shouldn't be worth handling
            return

        if text.startswith('/ipfs/'):
            # The clipboard contains a full IPFS path
            ma = cidhelpers.ipfsRegSearch(text)
            if ma:
                cid = ma.group(1)
                if not cidhelpers.cidValid(cid):
                    return
                path = joinIpfs(cid)
                if ma.group(2):
                    path += ma.group(2)
                self.hRecord(path)
                self.clipboardHasIpfs.emit(True, ma.group(1), path)
        elif text.startswith('/ipns/'):
            # The clipboard contains a full IPNS path
            ma = cidhelpers.ipnsRegSearch(text)
            if ma:
                path = text
                self.hRecord(path)
                self.clipboardHasIpfs.emit(True, None, path)
        elif cidhelpers.cidValid(text):
            # The clipboard simply contains a CID
            path = joinIpfs(text)
            self.hRecord(path)
            self.clipboardHasIpfs.emit(True, text, path)
        else:
            # Not a CID/path
            self.clipboardHasIpfs.emit(False, None, None)

    def hLookup(self, path):
        for hTs, hItem in self.history.items():
            if hItem['path'] == path:
                return hItem

    def hRecord(self, path):
        """ Records an item in the history and emits a signal """
        now = time.time()
        if self.hLookup(path):
            return
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
        mode = QClipboard.Clipboard
        if self.clipboard.supportsSelection():
            mode = QClipboard.Selection
        return mode

    def setText(self, text):
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
            listing = pkg_resources.resource_listdir('docs.manual', '')
            for entry in listing:
                if entry.startswith('__'):
                    continue
                self.importManualLang(entry)
        except Exception as e:
            self.app.debug(str(e))

    def importManualLang(self, lang):
        try:
            docPath = pkg_resources.resource_filename('docs.manual',
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
            self.app.documentationAvailable.emit(lang, docEntry)
