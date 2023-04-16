import functools
import os.path
import os
import aioipfs

from PyQt5.QtWebEngineWidgets import QWebEngineDownloadItem
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import QObject

from galacteek import log
from galacteek import logUser
from galacteek import ensure
from galacteek.ipfs import ipfsOp
from galacteek.ipfs.crawl import runTitleParser
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ipfs.cidhelpers import qurlPercentDecode
from galacteek.core.asynclib import asyncReadFile
from galacteek.core.asynclib import asyncWriteFile

from galacteek.ld.rdf import hashmarks as rdf_hashmarks

from .helpers import runDialog
from .dialogs import DownloadOpenObjectDialog
from ..appsettings import *
from .i18n import iUnknown
from .i18n import iDownload


def iFinishedDownload(filename):
    return QCoreApplication.translate(
        'Galacteek', 'Finished downloading file {0}').format(filename)


def iStartingDownload(filename):
    return QCoreApplication.translate(
        'Galacteek', 'Downloading file {0} ..').format(filename)


def iPageSaved(title):
    return QCoreApplication.translate(
        'Galacteek',
        'Web page {0} was saved').format(title)


class DownloadsManager(QObject):
    def __init__(self, app):
        super(DownloadsManager, self).__init__(app)
        self.app = app

    def shouldAutoOpen(self, iPath):
        autoOpenExtensions = ['.pdf']
        fname, ext = os.path.splitext(iPath.basename)
        return ext in autoOpenExtensions

    def onDownloadRequested(self, downItem: QWebEngineDownloadItem) -> None:
        downPath = downItem.path()
        downUrl = downItem.url()

        if downPath.startswith(self.app.tempDirWeb) or \
           downPath.startswith(self.app.tempDirArchive):
            downItem.finished.connect(
                functools.partial(self.pageSaved, downItem))
            downItem.accept()

            return

        iPath = IPFSPath(qurlPercentDecode(downUrl), autoCidConv=True)
        dialogPrechoice = 'download'
        allowOpen = False

        if iPath.valid:
            allowOpen = True
            if iPath.basename and self.shouldAutoOpen(iPath):
                dialogPrechoice = 'open'

        return runDialog(DownloadOpenObjectDialog,
                         iPath.ipfsUrl if iPath.valid else downUrl.toString(),
                         downItem,
                         dialogPrechoice,
                         allowOpen,
                         accepted=self.onDialogAccepted)

    def onDownloadProgress(self, received, total):
        pass

    def onDownloadFinished(self, item):
        filename = item.path() or iUnknown()
        self.app.systemTrayMessage(
            iDownload(), iFinishedDownload(filename))

    def onDialogAccepted(self, dialog):
        choice = dialog.choice()
        downItem = dialog.downloadItem

        downPath = downItem.path()
        name = os.path.basename(downPath)

        if choice == 0:
            downloadsLoc = self.app.settingsMgr.eGet(S_DOWNLOADS_PATH)

            self.app.systemTrayMessage(iDownload(), iStartingDownload(name))

            downItem.setPath(os.path.join(downloadsLoc, name))
            downItem.finished.connect(functools.partial(
                self.onDownloadFinished, downItem))
            downItem.accept()
        elif choice == 1:
            downItem.cancel()

            iPath = IPFSPath(dialog.objectUrl)
            if iPath.valid:
                ensure(self.app.resourceOpener.open(iPath))

    def pageSaved(self, downItem: QWebEngineDownloadItem) -> None:
        saveFormat = downItem.savePageFormat()

        if saveFormat == QWebEngineDownloadItem.CompleteHtmlSaveFormat:
            ensure(self.pageSavedComplete(downItem))

    @ipfsOp
    async def pageSavedComplete(self, ipfsop,
                                downItem: QWebEngineDownloadItem):
        curProfile = ipfsop.ctx.currentProfile

        path = downItem.path()
        basedir = os.path.dirname(path)

        data = await asyncReadFile(path)
        if data is None:
            return

        # Rewrite links that have the gateway origin
        try:
            decoded = data.decode()
            params = self.app.getIpfsConnectionParams()
            replaced = decoded.replace(str(params.gatewayUrl), 'dweb:')
        except:
            # No rewrite
            pass
        else:
            await asyncWriteFile(path, replaced.encode())

        title = runTitleParser(data)
        if title is None:
            title = iUnknown()

        try:
            entry = await ipfsop.addPath(basedir)

            assert entry
        except aioipfs.APIError as err:
            log.debug(f'Cannot import saved page: {err.message}')
        else:
            cid = entry.get('Hash')

            logUser.debug(f'Saved webpage with CID: {cid}')

            if path.startswith(self.app.tempDirArchive):
                # Archive: register a hashmark for it
                iPath = IPFSPath(cid)
                await rdf_hashmarks.addLdHashmark(iPath, title)
            elif path.startswith(self.app.tempDirWeb):
                if curProfile and cid:
                    await curProfile.webPageSaved.emit(entry, title)

                self.app.systemTrayMessage('Downloads', iPageSaved(title))
