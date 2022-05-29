from PyQt5.QtCore import QCoreApplication


def iIpfsNetwork():
    return QCoreApplication.translate('Galacteek', 'IPFS network')


def iNoIpfsNetwork():
    return QCoreApplication.translate('Galacteek', 'No IPFS network')


def iCurrentIpfsNetwork(netName):
    return QCoreApplication.translate(
        'Galacteek',
        'Current IPFS network: {}').format(netName)


# IPFS daemon messages


def iIpfsDaemon():
    return QCoreApplication.translate('Galacteek', 'IPFS daemon')


def iIpfsDaemonProcessControl():
    return QCoreApplication.translate('Galacteek', 'IPFS daemon process')


def iIpfsDaemonCPUPriority():
    return QCoreApplication.translate('Galacteek', 'CPU priority (nice)')


def iIpfsDaemonIOPriority():
    return QCoreApplication.translate('Galacteek', 'IO priority')


def iIpfsDaemonStarted():
    return QCoreApplication.translate('Galacteek', 'IPFS daemon started')


def iIpfsDaemonResumed():
    return QCoreApplication.translate(
        'Galacteek',
        'IPFS daemon was already running (no start)'
    )


def iIpfsDaemonGwStarted():
    return QCoreApplication.translate('Galacteek',
                                      "IPFS daemon's gateway started")


def iIpfsDaemonReady():
    return QCoreApplication.translate('Galacteek', 'IPFS daemon is ready')


def iIpfsDaemonProblem():
    return QCoreApplication.translate('Galacteek',
                                      'Problem starting IPFS daemon')


def iIpfsDaemonInitProblem():
    return QCoreApplication.translate(
        'Galacteek',
        'Problem initializing the IPFS daemon (check the ports configuration)')


def iIpfsDaemonWaiting(count):
    return QCoreApplication.translate(
        'Galacteek',
        'IPFS daemon: waiting for connection (try {0})'.format(count))


def iIpfsDaemonKeepRunningAsk():
    return QCoreApplication.translate(
        'Galacteek',
        'Do you want to keep the IPFS daemon running ?'
    )


def iFsRepoMigrateNotFound():
    return QCoreApplication.translate(
        'Galacteek',
        'Warning: could not find IPFS repository migration tool')


def iGoIpfsNotFound():
    return QCoreApplication.translate(
        'Galacteek',
        'Error: Could not find go-ipfs on your system')


def iGoIpfsTooOld():
    return QCoreApplication.translate(
        'Galacteek',
        'Error: go-ipfs version found on your system is too old')


def iGoIpfsFetchAsk():
    return QCoreApplication.translate(
        'Galacteek',
        'go-ipfs was not found on your system: download '
        'binary from IPFS distributions website (https://dist.ipfs.io) ?')


def iGoIpfsFetchTimeout():
    return QCoreApplication.translate(
        'Galacteek',
        'Timeout while fetching go-ipfs distribution')


def iGoIpfsFetchSuccess():
    return QCoreApplication.translate(
        'Galacteek',
        'go-ipfs was installed successfully')


def iGoIpfsFetchError():
    return QCoreApplication.translate(
        'Galacteek',
        'Error while fetching go-ipfs distribution')
