#
# Galacteek, GUI startup entry point

import asyncio
import sys
import argparse
import os, os.path
import time
import shutil

from PyQt5.QtWidgets import QApplication, QMainWindow

from galacteek.ipfs import ipfsd
from galacteek.ui import mainui
from galacteek import application
from galacteek.appsettings import *

def galacteekGui(args):
    from PyQt5.QtWidgets import QApplication, QDialog

    gApp = application.GalacteekApplication(profile=args.profile,
            debug=args.debug)
    loop = gApp.setupAsyncLoop()
    sManager = gApp.settingsMgr

    if args.apiport:
        sManager.setSetting(section, CFG_KEY_APIPORT,  args.apiport)
    if args.swarmport:
        sManager.setSetting(section, CFG_KEY_SWARMPORT, args.swarmport)
    if args.gatewayport:
        sManager.setSetting(section, CFG_KEY_HTTPGWPORT, args.gatewayport)

    # Look if we can find the ipfs executable
    ipfsPath = shutil.which('ipfs')
    if not ipfsPath:
        gApp.systemTrayMessage('IPFS',
            'Could not find go-ipfs on your system')

    if ipfsPath and sManager.isTrue(CFG_SECTION_IPFSD, CFG_KEY_ENABLED):
        gApp.startIpfsDaemon()
    else:
        gApp.updateIpfsClient()

    gApp.startPinner()

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
