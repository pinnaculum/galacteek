#
# Galacteek, GUI startup entry point

import asyncio
import sys
import argparse
import os, os.path
import time
import shutil

from PyQt5.QtWidgets import QApplication, QMainWindow
from quamash import QEventLoop, QThreadExecutor

from galacteek.ipfs import ipfsd
from galacteek.ui import mainui
from galacteek import application
from galacteek.appsettings import *

def galacteekGui(args):
    from PyQt5.QtWidgets import QApplication, QDialog

    shApp = application.GalacteekApplication(profile=args.profile,
            debug=args.debug)
    loop = QEventLoop(shApp)
    asyncio.set_event_loop(loop)
    shApp.setLoop(loop)

    # Sets the default settings
    sManager = shApp.settingsMgr
    section = CFG_SECTION_IPFSD

    sManager.setDefaultSetting(section, CFG_KEY_APIPORT, 5008)
    sManager.setDefaultSetting(section, CFG_KEY_SWARMPORT, 4008)
    sManager.setDefaultSetting(section, CFG_KEY_HTTPGWPORT, 8081)
    sManager.setDefaultSetting(section, CFG_KEY_SWARMHIGHWATER, 50)
    sManager.setDefaultTrue(section, CFG_KEY_ENABLED)

    if args.apiport:
        sManager.setSetting(section, CFG_KEY_APIPORT,  args.apiport)
    if args.swarmport:
        sManager.setSetting(section, CFG_KEY_SWARMPORT, args.swarmport)
    if args.gatewayport:
        sManager.setSetting(section, CFG_KEY_HTTPGWPORT, args.gatewayport)

    sManager.setDefaultSetting(section, CFG_KEY_SWARMLOWWATER, 10)

    section = CFG_SECTION_BROWSER
    sManager.setDefaultSetting(section, CFG_KEY_HOMEURL, 'fs:/ipns/ipfs.io')
    sManager.setDefaultSetting(section, CFG_KEY_DLPATH,
        shApp.defaultDownloadsLocation)
    sManager.setDefaultTrue(section, CFG_KEY_GOTOHOME)

    # Default IPFS connection when not spawning daemon
    section = CFG_SECTION_IPFSCONN1
    sManager.setDefaultSetting(section, CFG_KEY_APIPORT, 5001)
    sManager.setDefaultSetting(section, CFG_KEY_HOST, 'localhost')
    sManager.setDefaultSetting(section, CFG_KEY_HTTPGWPORT, 8080)

    section = CFG_SECTION_IPFS
    sManager.setDefaultTrue(section, CFG_KEY_PUBSUB)
    sManager.sync()

    # Look if we can find the ipfs executable
    ipfsPath = shutil.which('ipfs')
    if not ipfsPath:
        shApp.systemTrayMessage('IPFS',
            'Could not find go-ipfs on your system')

    if ipfsPath and sManager.isTrue(CFG_SECTION_IPFSD, CFG_KEY_ENABLED):
        shApp.startIpfsDaemon()
    else:
        shApp.updateIpfsClient()

    shApp.startPinner()
    #shApp.mainWindow.show()

    # Use the context manager so loop cleanup/close is automatic
    with loop:
        loop.run_forever()

def start():
    parser = argparse.ArgumentParser()

    parser.add_argument('--apiport',  default=None,
        help='IPFS API port number')
    parser.add_argument('--swarmport', default=None,
        help='IPFS swarm port number')
    parser.add_argument('--gatewayport', default=None,
        help='IPFS http gateway port number')
    parser.add_argument('--profile', default='main',
        help='Profile')
    parser.add_argument('-d', action='store_true',
        dest='debug', help = 'Activate debugging')
    args = parser.parse_args()

    galacteekGui(args)
