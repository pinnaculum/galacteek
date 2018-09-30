
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

def iConnectStatus(id, agent, peerscount):
    return QCoreApplication.translate('GalacteekWindow',
        'IPFS node: {0} ({1}): connected to {2} peer(s)').format(
        id, agent, peerscount)

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
    return QCoreApplication.translate('IPFSTreeView', 'Name')
def iFileSize():
    return QCoreApplication.translate('IPFSTreeView', 'Size')
def iFileHash():
    return QCoreApplication.translate('IPFSTreeView', 'Hash')
def iMimeType():
    return QCoreApplication.translate('IPFSTreeView', 'Mime type')
def iUnknown():
    return QCoreApplication.translate('IPFSTreeView', 'Unknown')

def iPinSuccess(path):
    return QCoreApplication.translate('GalacteekWindow',
        '{0} was pinned successfully').format(path)

def iManual():
    return QCoreApplication.translate('GalacteekWindow', 'Manual')

def iHashmark():
    return QCoreApplication.translate('GalacteekWindow', 'Hashmark')

def iDownload():
    return QCoreApplication.translate('GalacteekWindow', 'Download')

def iMediaPlayer():
    return QCoreApplication.translate('GalacteekWindow', 'Media Player')

def iLangEnglish():
    return QCoreApplication.translate('Galacteek', 'English')

def iLangFrench():
    return QCoreApplication.translate('Galacteek', 'French')

def iYes():
    return QCoreApplication.translate('Galacteek', 'yes')

def iNo():
    return QCoreApplication.translate('Galacteek', 'no')

def iDelete():
    return QCoreApplication.translate('Galacteek', 'Delete')

def iInvalidInput():
    return QCoreApplication.translate('Galacteek', 'Invalid input')

def iKey():
    return QCoreApplication.translate('Galacteek', 'Key')

def iValue():
    return QCoreApplication.translate('Galacteek', 'Value')

def iMerkleLink():
    return QCoreApplication.translate('Galacteek', 'Merkle link')

def iIpfsInfos():
    return QCoreApplication.translate('GalacteekWindow', 'IPFS informations')

def iNoTitle():
    return QCoreApplication.translate('GalacteekWindow', 'No title')

def iFinished():
    return QCoreApplication.translate('GalacteekWindow', 'Finished')

# IPFS daemon ui messages

def iFsRepoMigrateNotFound():
    return QCoreApplication.translate('Galacteek',
        'Warning: could not find IPFS repository migration tool on your system')

def iGoIpfsNotFound():
    return QCoreApplication.translate('Galacteek',
        'Error: Could not find go-ipfs on your system')

def iGoIpfsTooOld():
    return QCoreApplication.translate('Galacteek',
        'Error: go-ipfs version found on your system is too old')

def iGoIpfsFetchAsk():
    return QCoreApplication.translate('Galacteek',
        'go-ipfs was not found on your system: download ' +
        'binary from IPFS distributions website (https://dist.ipfs.io) ?')

def iGoIpfsFetchTimeout():
    return QCoreApplication.translate('Galacteek',
        'Timeout while fetching go-ipfs distribution')

def iGoIpfsFetchSuccess():
    return QCoreApplication.translate('Galacteek',
        'go-ipfs was installed successfully')

def iGoIpfsFetchError():
    return QCoreApplication.translate('Galacteek',
        'Error while fetching go-ipfs distribution')

def iNewReleaseAvailable():
    return QCoreApplication.translate('Galacteek',
        'New release available: upgrade with pip install -U galacteek')
