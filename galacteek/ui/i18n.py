
import PyQt5.QtCore

from PyQt5.QtCore import QCoreApplication

def qtr(ctx, msg):
    return QCoreApplication.translate(ctx, msg)

# Main window messages
def iNoStatus():
    return QCoreApplication.translate('GalacteekWindow', 'No status')

def iGeneralError(msg):
    return QCoreApplication.translate('GalacteekWindow',
        'General error: {0}').format(msg)

def iErrNoCx():
    return QCoreApplication.translate('GalacteekWindow',
        'No connection available')

def iCxButNoPeers(id, agent):
    return QCoreApplication.translate('GalacteekWindow',
        'IPFS node: {0} ({1}): not connected to any peers').format(
        id, agent)

def iConnectStatus(id, agent, peercount):
    return QCoreApplication.translate('GalacteekWindow',
        'IPFS node: {0} ({1}): connected to {2} peer(s)').format(
        id, agent, peercount)

def iItemsInPinningQueue(items):
    return QCoreApplication.translate('GalacteekWindow',
        'Items in pinning queue: {}'.format(items))

def iUnknown():
    return QCoreApplication.translate('GalacteekWindow', 'Unknown')

def iUnknownAgent():
    return QCoreApplication.translate('GalacteekWindow', 'Unknown agent')

def iMinimized():
    return QCoreApplication.translate('GalacteekWindow',
            'Galacteek was minimized to tray')

# Headers used in the various tree widgets
def iFileName():
    return QCoreApplication.translate('TreeView', 'Name')
def iFileSize():
    return QCoreApplication.translate('TreeView', 'Size')
def iFileHash():
    return QCoreApplication.translate('TreeView', 'Hash')
def iMimeType():
    return QCoreApplication.translate('TreeView', 'Mime type')
def iUnknown():
    return QCoreApplication.translate('TreeView', 'Unknown')

def iPinSuccess(path):
    return QCoreApplication.translate('GalacteekWindow',
        '{0} was pinned successfully').format(path)

def iManual():
    return QCoreApplication.translate('GalacteekWindow', 'Manual')
