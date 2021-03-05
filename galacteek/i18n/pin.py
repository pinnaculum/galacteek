from PyQt5.QtCore import QCoreApplication


def iItemsInPinningQueue(itemsCount):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Items queued for pinning: {}'.format(itemsCount))


def iBrowseAutoPin():
    return QCoreApplication.translate('GalacteekWindow', 'Browse (auto-pin)')


def iPinSuccess(path):
    return QCoreApplication.translate(
        'GalacteekWindow',
        '{0} was pinned successfully').format(path)


def iPinError(path, errmsg):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Error pinning {0}: {1}').format(path, errmsg)


def iPinningStatus():
    return QCoreApplication.translate('GalacteekWindow', 'Pinning status')


def iPinned():
    return QCoreApplication.translate('GalacteekWindow', 'Pinned')


def iPinning():
    return QCoreApplication.translate('GalacteekWindow', 'Pinning')


def iPinningProgress(nodes, secsSinceUpdate):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Pin: {0} nodes retrieved ({1}s since last update)'
    ).format(nodes, secsSinceUpdate)


def iPinningStalled():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Pinning stalled'
    )


def iPin():
    return QCoreApplication.translate('GalacteekWindow', 'Pin')


def iPinAndDownload():
    return QCoreApplication.translate('GalacteekWindow', 'Pin and download')


def iPinDirectory():
    return QCoreApplication.translate('GalacteekWindow', 'Pin directory')


def iUnpin():
    return QCoreApplication.translate('GalacteekWindow', 'Unpin')


def iPinSingle():
    return QCoreApplication.translate('GalacteekWindow', 'Pin (single)')


def iPinRecursive():
    return QCoreApplication.translate('GalacteekWindow', 'Pin (recursive)')


def iPinRecursiveParent():
    return QCoreApplication.translate('GalacteekWindow',
                                      'Pin parent (recursive)')


def iPinPageLinks():
    return QCoreApplication.translate('GalacteekWindow', "Pin page's links")


def iBatchPin():
    return QCoreApplication.translate('GalacteekWindow', 'Batch pin')


def iDoNotPin():
    return QCoreApplication.translate('GalacteekWindow', 'Do not pin')


def iGlobalAutoPinning():
    return QCoreApplication.translate('GalacteekWindow',
                                      'Global automatic pinning')


def iPinataInstructions():
    return QCoreApplication.translate(
        'GalacteekWindow',
        '''
        <p>
            Please first <a href="https://pinata.cloud/signup">
            sign up for an account at Pinata</a>.
        </p>
        '''
    )


def iPinToRemoteSingle(serviceName):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Pin to remote: {}'
    ).format(serviceName)


def iPinToRemoteRecursive(serviceName):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Pin to remote: {} (recursive)'
    ).format(serviceName)
