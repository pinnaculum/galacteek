from PyQt5.QtCore import QCoreApplication


def iErrNoCx():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'No connection available')


def iCxButNoPeers(id, agent):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'IPFS ({1}): not connected to any peers').format(
        id, agent)


def iConnectStatus(id, agent, peerscount):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'IPFS ({1}): connected to {2} peer(s)').format(
        id, agent, peerscount)
