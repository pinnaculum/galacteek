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


def iPinningOptions():
    return QCoreApplication.translate('GalacteekWindow', 'Pinning options')


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


def iPinHere():
    return QCoreApplication.translate('GalacteekWindow', 'Pin (here)')


def iPinThisPage():
    return QCoreApplication.translate('BrowserTabForm', 'Pin (this page)')


def iPinAndDownload():
    return QCoreApplication.translate('GalacteekWindow', 'Pin and download')


def iPinDirectory():
    return QCoreApplication.translate('GalacteekWindow', 'Pin directory')


def iUnpin():
    return QCoreApplication.translate('GalacteekWindow', 'Unpin')


def iUnpinHere():
    return QCoreApplication.translate('GalacteekWindow', 'Unpin (here)')


def iUnpinHereOk():
    return QCoreApplication.translate(
        'GalacteekWindow',
        '''
        <p>
        The content was <b>unpinned</b> from your node..
        It will disappear from your repository after
        the next garbage-collection.
        </p>
        '''
    )


def iUnpinFromRpsOk():
    return QCoreApplication.translate(
        'GalacteekWindow',
        '''
        <p>
        The content was <b>unpinned</b> by the remote service.
        </p>
        '''
    )


def iUnpinError():
    return QCoreApplication.translate('GalacteekWindow', 'Unpin error')


def iPinSingle():
    return QCoreApplication.translate('GalacteekWindow', 'Pin (single)')


def iPinHereRecursive():
    return QCoreApplication.translate(
        'GalacteekWindow', 'Pin (here, recursive)')


def iPinRecursive():
    return QCoreApplication.translate('GalacteekWindow', 'Pin (recursive)')


def iPinRecursiveParent():
    return QCoreApplication.translate('GalacteekWindow',
                                      'Pin parent (recursive)')


def iPinHereRecursiveParent():
    return QCoreApplication.translate('GalacteekWindow',
                                      'Pin parent (here, recursive)')


def iPinPageLinks():
    return QCoreApplication.translate('GalacteekWindow', "Pin page's links")


def iBatchPin():
    return QCoreApplication.translate('GalacteekWindow', 'Batch pin')


def iDoNotPin():
    return QCoreApplication.translate('GalacteekWindow', 'Do not pin')


def iGlobalAutoPinning():
    return QCoreApplication.translate('GalacteekWindow',
                                      'Global automatic pinning')


def iPinningFury():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Pinning Fury (go wild)'
    )


def iPinataInstructions():
    return QCoreApplication.translate(
        'GalacteekWindow',
        '''
        <p>
            Please first <a href="https://pinata.cloud/signup">
            sign up for an account at Pinata</a>.
        </p>
        <p>
            Once registered, paste the pinning API key in the
            form field named <i>Key</i>.
        </p>
        '''
    )


def iPinToRps(serviceName):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Pin to remote service: {}'
    ).format(serviceName)


def iUnpinFromRps(serviceName):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Unpin from remote service: {}'
    ).format(serviceName)


def iUnpinFromRpsToolTip(serviceName):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Unpin from remote service: {}'
    ).format(serviceName)


def iPinToRpsWithName(serviceName):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Custom Pin to remote service: {}'
    ).format(serviceName)


def iPinToRpsToolTip(serviceName):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Pin this content to the remote '
        'pinning service named {}'
    ).format(serviceName)


def iPinToRpsSuccess(serviceName, path):
    return QCoreApplication.translate(
        'GalacteekWindow',
        '<b>{}</b>: Your content was successfully queued for '
        'pinning on the remote pinning service'
    ).format(serviceName)


def iPinToRpsError(serviceName, path):
    return QCoreApplication.translate(
        'GalacteekWindow',
        '<b>{}</b>: An error ocurred with the remote '
        'pinning service'
    ).format(serviceName)


def iPinToAllRps():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Pin to all remote services'
    )


def iPinToAllRpsToolTip():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Pin this content to all remote pinning '
        'services configured'
    )


def iRpsStatusSummary(service, status, pinned, pinning, queued, failed):
    return QCoreApplication.translate(
        'GalacteekWindow',
        f'''
        <div>
        <p>Remote pinning service: <b>{service}</b></p>
        <p>{status}</p>
        <ul>
            <li><b>PIND: {pinned} objects</b></li>
            <li><b>PINNING: {pinning} objects</b></li>
            <li><b>INQUEUE: {queued} objects</b></li>
            <li><b>FAIL: {failed} objects</b></li>
        </ul>
        </div>
        '''
    ).format(service, status, pinned, pinning, queued, failed)


def iRpsStatusOk():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Remote Pinning Service active'
    )


def iRpsStatusPinning():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Remote Pinning Service: Pinning in progress'
    )


def iRpsStatusPinnedObjCount(count):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Remote Pinning Service: Have pinned: {}'
    ).format(count)


def iRpsStatusSomeFail():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Remote Pinning Service: Some failures'
    )
