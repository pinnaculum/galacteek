from PyQt5.QtCore import QCoreApplication

# Headers used in the various tree widgets


def iPath():
    return QCoreApplication.translate('IPFSTreeView', 'Path')


def iCidOrPath():
    return QCoreApplication.translate('IPFSTreeView', 'CID or path')


def iFileName():
    return QCoreApplication.translate('IPFSTreeView', 'Name')


def iFileSize():
    return QCoreApplication.translate('IPFSTreeView', 'Size')


def iFileHash():
    return QCoreApplication.translate('IPFSTreeView', 'Hash')


def iMultihash():
    return QCoreApplication.translate('IPFSTreeView', 'Multihash')


def iMimeType():
    return QCoreApplication.translate('IPFSTreeView', 'MIME type')
