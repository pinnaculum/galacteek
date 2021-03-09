from PyQt5.QtCore import QCoreApplication

# CID


def iCID():
    return QCoreApplication.translate('GalacteekWindow', 'CID')


def iCIDv0():
    return QCoreApplication.translate('GalacteekWindow', 'CIDv0')


def iCIDv1():
    return QCoreApplication.translate('GalacteekWindow', 'CIDv1')


def iInvalidCID():
    return QCoreApplication.translate('GalacteekWindow', 'Invalid CID')


def iP2PKey():
    return QCoreApplication.translate('GalacteekWindow', 'P2P key')


def iUnixFSNode():
    return QCoreApplication.translate('GalacteekWindow', 'UnixFS node')


def iUnixFSFileToolTip(eInfo):
    return QCoreApplication.translate(
        'IPFSHashExplorer',
        '''
        <p><b>{0}</b></p>
        <p>MIME type: {1}</p>
        <p>CID: {2}</p>
        <p>Size: {3}</p>
        ''').format(
            eInfo.filename,
            eInfo.mimeType,
            eInfo.cid,
            eInfo.sizeFormatted
    )


# URL types

def iIPFSUrlTypeNative():
    return QCoreApplication.translate('GalacteekWindow', 'IPFS URL: native')


def iIPFSUrlTypeHttpGateway():
    return QCoreApplication.translate(
        'GalacteekWindow', 'IPFS URL: gatewayed')


def iMerkleLink():
    return QCoreApplication.translate('Galacteek', 'Merkle link')


def iIpfsInfos():
    return QCoreApplication.translate('GalacteekWindow', 'IPFS informations')


def iIpfsQrCodes():
    return QCoreApplication.translate('GalacteekWindow', 'IPFS QR codes')


def iIpfsQrEncode():
    return QCoreApplication.translate('GalacteekWindow', 'QR encoding')


def iProvidedByPeers(count):
    return QCoreApplication.translate(
        'Galacteek',
        'Provided by {} peer(s)'
    ).format(count)


def iProvidedByPeersShort(count):
    return QCoreApplication.translate(
        'Galacteek',
        'PINNED: {}P'
    ).format(count)


def iProvidedByAtLeastPeers(count):
    return QCoreApplication.translate(
        'Galacteek',
        'Provided by at least {} peer(s)'
    ).format(count)


def iNotProvidedByAnyPeers():
    return QCoreApplication.translate(
        'Galacteek',
        'No one seems to have this file ..'
    )


def iSearchingProviders():
    return QCoreApplication.translate(
        'Galacteek',
        'Searching providers ..'
    )


def iGarbageCollectRun():
    return QCoreApplication.translate(
        'GalacteekWindow', 'Run the garbage collector')


def iGarbageCollectRunAsk():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Do you want to run the garbage collector '
        'on your repository ?'
    )


def iGarbageCollector():
    return QCoreApplication.translate(
        'GalacteekWindow', 'Garbage collector')


def iGCPurgedObject(cid):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Purged object with CID: {0}').format(cid)


def iIpfsError(msg):
    return QCoreApplication.translate('GalacteekWindow',
                                      'IPFS error: {0}').format(msg)


def iCannotResolve(objPath):
    return QCoreApplication.translate(
        'Galacteek',
        'Cannot resolve object: <b>{}</b>').format(objPath)


def iResourceCannotOpen(path):
    return QCoreApplication.translate(
        'ResourceOpener',
        '{}: unable to determine resource type'
    ).format(path)


def iFollowIpldLink():
    return QCoreApplication.translate(
        'ResourceOpener',
        'Follow IPLD link'
    )
