
import sys
import json
import os, os.path
import multiprocessing
import time
import asyncio

from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtCore import (QCoreApplication, QUrl, QStandardPaths,
        QSettings, QTranslator)

from galacteek.ipfs import pinning, ipfsd, asyncipfsd
from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.pubsub import *
from galacteek.ui import mainui, galacteek_rc, downloads
from galacteek.ui.helpers import *
from galacteek.appsettings import *
from galacteek.core.marks import Bookmarks

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

class GalacteekApplication(QApplication):
    def __init__(self):
        QApplication.__init__(self, sys.argv)

        self._loop = None
        self._client = None
        self._pubsubListeners = []
        self.ipfsd = None
        self.pubsubEnabled = False

        self.mainWindow = None

        self.setupTranslator()
        self.initSettings()
        self.initPaths()
        self.initSystemTray()
        self.initMisc()

    @property
    def ipfsConnParams(self):
        return self.getIpfsConnectionParams()

    def initSettings(self):
        QCoreApplication.setOrganizationName('galacteek')
        QCoreApplication.setApplicationName('galacteek')

        self.settingsMgr = SettingsManager()

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
        self.bookmarks = Bookmarks()

    def setupTranslator(self):
        self.translator = QTranslator()
        self.translator.load(':/share/translations/galacteek_en.qm')
        QApplication.installTranslator(self.translator)

    def createMainWindow(self):
        self.mainWindow = mainui.MainWindow(self)
        self.mainWindow.loop = self.getLoop()
        self.mainWindow.ipfsClient = self.getIpfsClient()
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
        self.systemTray.showMessage(title, message,
            QSystemTrayIcon.Information, timeout)

    def setupRepository(self):
        async def setup(oper):
            rootList = await oper.filesList('/')
            if not rootList:
                return
            hasGalacteek = await oper.filesLookup('/', 'galacteek')
            if not hasGalacteek:
                await oper.client.files.mkdir(GFILES_MYFILES_PATH, parents=True)

        self.ipfsTaskOp(setup)

    def ipfsTask(self, fn, *args, **kw):
        self.getLoop().create_task(fn(self.getIpfsClient(),
            *args, **kw))

    def ipfsTaskOp(self, fn, *args, **kw):
        client = self.getIpfsClient()
        self.getLoop().create_task(fn(IPFSOperator(client),
            *args, **kw))

    def setIpfsd(self, ipd):
        self.ipfsd = ipd

    def setIpfsClient(self, client):
        self._client = client

    def getIpfsClient(self):
        return self._client

    def getIpfsConnectionParams(self):
        mgr = self.settingsMgr
        section = CFG_SECTION_IPFSD
        if mgr.isTrue(section, CFG_KEY_ENABLED):
            return IPFSConnectionParams('localhost',
                    mgr.getSetting(section, 'apiport'),
                    mgr.getSetting(section, 'httpgwport')
            )
        else:
            section = CFG_SECTION_IPFSCONN1
            return IPFSConnectionParams(
                    mgr.getSetting(section, 'host'),
                    mgr.getSetting(section, 'apiport'),
                    mgr.getSetting(section, 'httpgwport')
            )

    def updateIpfsClient(self):
        pClient = self.getIpfsClient()
        if pClient:
            pass
        connParams = self.getIpfsConnectionParams()
        client = aioipfs.AsyncIPFS(host=connParams.getHost(),
                port=connParams.getApiPort(), loop=self.getLoop())
        self.setIpfsClient(client)
        self.setupRepository()

        self.setupIpfsServices()

    def setupIpfsServices(self):
        if self.pubsubEnabled:
            listener = PubsubListener(self.getIpfsClient(),
                loop=self.getLoop(), topic='galacteek.main')
            listener.start()
            self._pubsubListeners.append(listener)

    def startPinner(self):
        self.pinner = pinning.Pinner(self, self.getLoop())
        self.getLoop().create_task(self.pinner.process())

    def setLoop(self, loop):
        self._loop = loop

    def getLoop(self):
        return self._loop

    def initPaths(self):
        self.dataLocation = QStandardPaths.writableLocation(QStandardPaths.DataLocation)
        if not self.dataLocation:
            raise Exception('No writable data location found')
        self.ipfsDataLocation = os.path.join(self.dataLocation, 'ipfs')

        if not os.path.exists(self.ipfsDataLocation):
            os.makedirs(self.ipfsDataLocation)

        self.defaultDownloadsLocation = QStandardPaths.writableLocation(
            QStandardPaths.DownloadLocation)

    def getDataLocation(self):
        return self.dataLocation

    def getIpfsDataLocation(self):
        return self.ipfsDataLocation

    def startIpfsDaemon(self):
        if self.ipfsd: # we only support one daemon for now
            return

        sManager = self.settingsMgr
        section = CFG_SECTION_IPFSD

        # Instantiate an IPFS daemon using asyncipfsd and
        # start it in a task, monitoring the initialization process

        self.ipfsd = asyncipfsd.AsyncIPFSDaemon(self.getIpfsDataLocation(),
            apiport=sManager.getInt(section, CFG_KEY_APIPORT),
            swarmport=sManager.getInt(section, CFG_KEY_SWARMPORT),
            gatewayport=sManager.getInt(section, CFG_KEY_HTTPGWPORT),
            swarm_lowwater=sManager.getInt(section, CFG_KEY_SWARMLOWWATER),
            swarm_highwater=sManager.getInt(section, CFG_KEY_SWARMHIGHWATER))

        async def startDaemon(ipfsd):
            res = await ipfsd.start()

            if res:
                running = False
                self.systemTrayMessage('IPFS', iIpfsDaemonStarted(),
                    timeout=1000)
                for iters in range(0, 64):
                    await asyncio.sleep(0.2)
                    if ipfsd.proto.gatewayStarted and ipfsd.proto.apiStarted:
                        # Good to go
                        self.systemTrayMessage('IPFS',
                            iIpfsDaemonReady(), timeout=1000)
                        running = True
                        break

                if running is True:
                    # Update the client and open a browser
                    self.updateIpfsClient()
                    tab = self.mainWindow.addBrowserTab()
                else:
                    self.systemTrayMessage('IPFS', iIpfsDaemonInitProblem())
            else:
                self.systemTrayMessage('IPFS', iIpfsDaemonProblem())

        self.getLoop().create_task(startDaemon(self.ipfsd))
        return self.ipfsd

    def onExit(self):
        if self.ipfsd:
            self.ipfsd.stop()

        self.quit()
        sys.exit(1)
