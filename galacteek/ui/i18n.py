
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

def iErrNoPeers():
    return QCoreApplication.translate('GalacteekWindow',
        'Not connected to any peers')

def iConnectStatus(id, agent, peercount):
    return QCoreApplication.translate('GalacteekWindow',
        'IPFS node: {0} ({1}) connected to {2} peer(s)').format(
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

