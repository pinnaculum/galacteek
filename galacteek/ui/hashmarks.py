from PyQt5.QtCore import QCoreApplication

from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.cidhelpers import *

from .modelhelpers import *
from .helpers import *
from .dialogs import *
from .widgets import *
from .i18n import *


def iPath():
    return QCoreApplication.translate('HashmarksViewForm', 'Path')


def iTitle():
    return QCoreApplication.translate('HashmarksViewForm', 'Title')


def iShared():
    return QCoreApplication.translate('HashmarksViewForm', 'Shared')


def iDate():
    return QCoreApplication.translate('HashmarksViewForm', 'Date')


def iTimestamp():
    return QCoreApplication.translate('HashmarksViewForm', 'Timestamp')


def iAlreadyHashmarked():
    return QCoreApplication.translate('HashmarksViewForm',
                                      'Already Hashmarked')


def iImportHashmark():
    return QCoreApplication.translate('HashmarksViewForm',
                                      'Import hashmark to')


def iNetworkMarks():
    return QCoreApplication.translate('HashmarksViewForm', 'Network hashmarks')


def iFeeds():
    return QCoreApplication.translate('HashmarksViewForm', 'Feeds')


def addHashmark(hashmarks, path, title, description='', stats={},
                pin=False, pinRecursive=False):
    if hashmarks.search(path):
        messageBox(iAlreadyHashmarked())
        return False

    runDialog(AddHashmarkDialog, hashmarks, path, title, description, stats,
              pin=pin, pinRecursive=pinRecursive)
    return True
