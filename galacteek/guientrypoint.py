# Galacteek, GUI startup entry point

import asyncio
import sys
import argparse
import shutil

from PyQt5.QtWidgets import QApplication

from galacteek.ipfs import ipfsd
from galacteek.ui import mainui
from galacteek.ui.i18n import *
from galacteek import application
from galacteek.appsettings import *

def galacteekGui(args):
    gApp = application.GalacteekApplication(profile=args.profile,
            debug=args.debug)
    loop = gApp.setupAsyncLoop()
    sManager = gApp.settingsMgr

    section = CFG_SECTION_IPFSD
    if args.apiport:
        sManager.setSetting(section, CFG_KEY_APIPORT, args.apiport)
    if args.swarmport:
        sManager.setSetting(section, CFG_KEY_SWARMPORT, args.swarmport)
    if args.gatewayport:
        sManager.setSetting(section, CFG_KEY_HTTPGWPORT, args.gatewayport)

    if sManager.isTrue(CFG_SECTION_IPFSD, CFG_KEY_ENABLED):
        fsMigratePath = shutil.which('fs-repo-migrations')
        hasFsMigrate = fsMigratePath is not None

        if hasFsMigrate is False:
            gApp.systemTrayMessage('Galacteek', iFsRepoMigrateNotFound())

        # Look if we can find the ipfs executable
        ipfsPath = shutil.which('ipfs')
        if not ipfsPath:
            gApp.systemTrayMessage('Galacteek', iGoIpfsNotFound(), timeout=8000)
        else:
            gApp.startIpfsDaemon()
    else:
        gApp.updateIpfsClient()

    gApp.startPinner()
    gApp.mainWindow.addHashmarksTab()

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
        help='Application Profile')
    parser.add_argument('-d', action='store_true',
        dest='debug', help = 'Activate debugging')
    args = parser.parse_args()

    galacteekGui(args)
