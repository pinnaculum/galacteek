from PyQt5.QtCore import QCoreApplication

# Decentralized identifiers (IPID)


def iDID():
    return QCoreApplication.translate('GalacteekWindow', 'DID')


def iDIDLong():
    return QCoreApplication.translate(
        'GalacteekWindow', 'Decentralized Identifier')


def iIPID():
    return QCoreApplication.translate(
        'GalacteekWindow', 'IPID')


def iIPIDLong():
    return QCoreApplication.translate(
        'GalacteekWindow', 'InterPlanetary Identifier')


def iIPServices():
    return QCoreApplication.translate(
        'GalacteekWindow', 'InterPlanetary Services')
