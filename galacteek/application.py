
import sys
import json
import os, os.path
import multiprocessing
import time
import asyncio

from quamash import QEventLoop

from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtCore import (QCoreApplication, QUrl, QStandardPaths,
        QSettings, QTranslator, QFile, pyqtSignal, QObject)

from galacteek.ipfs import pinning, ipfsd, asyncipfsd
from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.pubsub import *
from galacteek.ipfs.feeds import FeedFollower

from galacteek.ui import mainui, galacteek_rc, downloads
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

    def __init__(self, debug=False, profile='main'):
        QApplication.__init__(self, sys.argv)

        QCoreApplication.setApplicationName(self.GALACTEEK_NAME)

        self.__profile = profile
        self._loop = None
        self._client = None

        self.mainWindow = None
        self.gWindows = []

        self.ipfsd = None
        self.pubsubListeners = []
        self.pinnerTask = None

        self.debugEnabled = debug

        self.ipfsCtx = IPFSContext()

        self.setupTranslator()
        self.setupPaths()

        self.initSettings()
        self.initSystemTray()
        self.initMisc()
        self.createMainWindow()

        self.setStyle()

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
            print(msg, file=sys.stderr)

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
        self.downloadsManager = downloads.DownloadsManager(self)
        self.marksLocal = IPFSMarks(self.localMarksFileLocation)
        self.marksNetwork = IPFSMarks(self.networkMarksFileLocation)

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
                IPFSOperator(client, ctx=self.ipfsCtx,
                debug=self.debugEnabled), *args, **kw))

    def setIpfsClient(self, client):
        self._client = client

    def getIpfsClient(self):
        return self._client

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
        #pClient = self.getIpfsClient()
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

        async def startDaemon(ipfsd):
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
                    # Update the client and open a browser tab
                    self.updateIpfsClient()
                    tab = self.mainWindow.addBrowserTab()
                else:
                    self.systemTrayMessage('IPFS', iIpfsDaemonInitProblem())
            else:
                self.systemTrayMessage('IPFS', iIpfsDaemonProblem())

        self.getLoop().create_task(startDaemon(self.ipfsd))
        return self.ipfsd

    def onExit(self):
        self.stopIpfsServices()
        if self.ipfsd:
            self.ipfsd.stop()

        self.quit()
        sys.exit(1)
