import os.path

from PyQt5 import QtWebEngineWidgets
from PyQt5.QtCore import QCoreApplication, QObject

from ..appsettings import *
from .i18n import iUnknown


def iFinishedDownload(filename):
    return QCoreApplication.translate(
        'Galacteek', 'Finished downloading file {0}').format(filename)


def iStartingDownload(filename):
    return QCoreApplication.translate(
        'Galacteek', 'Downloading file {0} ..').format(filename)


class DownloadsManager(QObject):
    def __init__(self, app):
        super(DownloadsManager, self).__init__()

        self.app = app
        self.webProfile = QtWebEngineWidgets.QWebEngineProfile.defaultProfile()
        self.webProfile.downloadRequested.connect(self.onDownloadRequested)

    def onDownloadRequested(self, downItem):
        if not downItem:
            return

        downloadsLoc = self.app.settingsMgr.eGet(S_DOWNLOADS_PATH)

        def progress(received, total):
            pass

        def finished(item):
            filename = item.path() or iUnknown()
            self.app.systemTrayMessage(
                'Galacteek', iFinishedDownload(filename))

        name = os.path.basename(downItem.path())

        self.app.systemTrayMessage('Galacteek', iStartingDownload(name))

        downItem.setPath(os.path.join(downloadsLoc, name))
        downItem.finished.connect(lambda: finished(downItem))
        downItem.downloadProgress.connect(progress)
        downItem.accept()
