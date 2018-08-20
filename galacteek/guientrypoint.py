# Galacteek, GUI startup entry point

import asyncio
import sys
import argparse
import shutil
import os.path

from PyQt5.QtWidgets import QApplication


from galacteek.ipfs import ipfsd, distipfsfetch
from galacteek.ui import mainui
from galacteek.ui.helpers import *
from galacteek.ui.i18n import *
from galacteek import application
from galacteek.appsettings import *

def whichIpfs():
    return shutil.which('ipfs')

async def fetchGoIpfsWrapper(app, timeout=60*10):
    try:
        await asyncio.wait_for(fetchGoIpfsDist(app), timeout)
    except asyncio.TimeoutError as e:
        app.mainWindow.statusMessage(iGoIpfsFetchTimeout())
        return None
    except Exception as e:
        app.mainWindow.statusMessage(iGoIpfsFetchError())
        return None
    else:
        app.mainWindow.statusMessage(iGoIpfsFetchSuccess())
        return whichIpfs()

async def fetchGoIpfsDist(app):
    async for msg in distipfsfetch.distIpfsExtract(
            dstdir=app.ipfsBinLocation, software='go-ipfs',
            executable='ipfs', version='0.4.17'):
        try:
            code, text = msg
            app.mainWindow.statusMessage(text)
        except Exception as e:
            app.debug(str(e))

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

        if hasFsMigrate is False and args.migrate is True:
            gApp.systemTrayMessage('Galacteek', iFsRepoMigrateNotFound())

        enableMigrate = hasFsMigrate is True and args.migrate is True

        # Look if we can find the ipfs executable
        ipfsPath = whichIpfs()
        if not ipfsPath:
            fetchWanted = questionBox('go-ipfs', iGoIpfsFetchAsk())

            def fetchFinished(fut):
                path = fut.result()
                if path is None:
                    gApp.systemTrayMessage('Galacteek',
                            iGoIpfsFetchError())
                else:
                    gApp.startIpfsDaemon(goIpfsPath=path,
                            migrateRepo=enableMigrate)

            if fetchWanted:
                fut = asyncio.ensure_future(fetchGoIpfsWrapper(gApp))
                fut.add_done_callback(fetchFinished)
            else:
                gApp.systemTrayMessage('Galacteek',
                        iGoIpfsNotFound())
        else:
            gApp.startIpfsDaemon(goIpfsPath=ipfsPath,
                    migrateRepo=enableMigrate)
    else:
        gApp.updateIpfsClient()

    gApp.startPinner()
    gApp.mainWindow.addHashmarksTab()

    if args.noreleasecheck is False:
        gApp.checkReleases()

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
    parser.add_argument('--migrate', action='store_true',
        dest='migrate', help = 'Activate automatic repository migration')
    parser.add_argument('--no-release-check', action='store_true',
        dest='noreleasecheck', help = "Don't check for new releases on PyPI")
    parser.add_argument('-d', action='store_true',
        dest='debug', help = 'Activate debugging')
    args = parser.parse_args()

    galacteekGui(args)
