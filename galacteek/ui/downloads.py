
import os.path

from PyQt5 import QtWebEngineWidgets, QtWebEngine, QtWebEngineCore
from PyQt5.QtCore import QCoreApplication

from ..appsettings import *

def iFinishedDownload(filename):
    return QCoreApplication.translate('Galacteek',
        'Finished downloading file {0}').format(filename)

class DownloadsManager(object):
    def __init__(self, app):
        self.app = app
        self.webProfile = QtWebEngineWidgets.QWebEngineProfile.defaultProfile()
        self.webProfile.downloadRequested.connect(self.onDownloadRequested)

    def onDownloadRequested(self, downitem):
        if not downitem:
            return

        downloadsLoc = self.app.settingsMgr.eGet(S_DOWNLOADS_PATH)

        def progress(received, total):
            pass

        def finished(item):
            filename = item.path() or 'Unknown'
            self.app.systemTrayMessage('Galacteek', iFinishedDownload(filename))

        downitem.setPath(os.path.join(downloadsLoc,
            os.path.basename(downitem.path())))

        downitem.finished.connect(lambda: finished(downitem))
        downitem.downloadProgress.connect(progress)
        downitem.accept()
