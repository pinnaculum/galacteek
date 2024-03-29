from PyQt5.QtCore import QCoreApplication

from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.cidhelpers import *

from ..helpers import *
from ..dialogs.hashmarks import AddHashmarkDialog
from ..widgets import *
from ..i18n import *


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


def iInvalidHashmarkPath():
    return QCoreApplication.translate('HashmarksViewForm',
                                      'Invalid hashmark path')


def iImportHashmark():
    return QCoreApplication.translate('HashmarksViewForm',
                                      'Import hashmark to')


def iNetworkMarks():
    return QCoreApplication.translate('HashmarksViewForm', 'Network hashmarks')


def iFeeds():
    return QCoreApplication.translate('HashmarksViewForm', 'Feeds')


def addHashmark(hashmarks, path, title, description='', stats={},
                pin=False, pinRecursive=False):
    if hashmarks.find(path):
        messageBox(iAlreadyHashmarked())
        return False

    ipfsPath = IPFSPath(path, autoCidConv=True)
    if not ipfsPath.valid:
        messageBox(iInvalidHashmarkPath())
        return False

    runDialog(AddHashmarkDialog, hashmarks,
              str(ipfsPath), title, description, stats,
              pin=pin, pinRecursive=pinRecursive)
    return True


async def addHashmarkAsync(path,
                           title: str = '',
                           description: str = '',
                           langTag: str = None,
                           pin=False, pinRecursive=False,
                           schemePreferred=None):
    await runDialogAsync(AddHashmarkDialog,
                         path, title, description,
                         langTag=langTag,
                         pin=pin, pinRecursive=pinRecursive,
                         schemePreferred=schemePreferred)
    return True
