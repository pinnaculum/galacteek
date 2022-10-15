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
            Please first sign up for an account at
            <a href="https://pinata.cloud/signup">Pinata</a>,
            <a href="https://api.web3.storage/">Web3.storage</a>,
            <a href="https://api.estuary.tech/pinning/">Estuary</a>,
            <a href="https://nft.storage/api">NFT Storage</a>,
            or any other IPFS remote pinning service.
        </p>
        <p>
            Once registered, copy-paste the API key in the
            form field below named <i>Key</i>.
        </p>
        '''
    )


def iWeb3StorageInstructions():
    return QCoreApplication.translate(
        'GalacteekWindow',
        '''
        <p>
            Please first <a href="https://web3.storage">
            sign up for an account at Web3.storage</a>.
        </p>
        <p>
            Once registered, paste the API token in the
            form field below named <i>Key</i>.
        </p>
        '''
    )


def iEstuaryTechInstructions():
    return QCoreApplication.translate(
        'GalacteekWindow',
        '''
        <p>
            Please first <a href="https://estuary.tech/sign-up">
            sign up for an account at Estuary.tech</a>.
        </p>
        <p>
            Once registered, paste the API token in the
            form field below named <i>Key</i>.
        </p>
        '''
    )


def iNftStorageInstructions():
    return QCoreApplication.translate(
        'GalacteekWindow',
        '''
        <p>
            Please first <a href="https://nft.storage/login/">
            sign up for an account at nft.storage</a>.
        </p>
        <p>
            Once registered, paste the API token in the
            form field below named <i>Key</i>.
        </p>
        '''
    )


def iCustomRpsInstructions():
    return QCoreApplication.translate(
        'GalacteekWindow',
        '''
        <p>
            Please set the custom endpoint address and the API key.
        </p>
        '''
    )


def iPinToRpsUnspecific():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Pin to a remote pinning service'
    )


def iPinPlaylistMediaChooseRps():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Pin playlist items to a remote service'
    )


def iPinPlaylistToRpsFinished(serviceName: str, count: int):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Pinned {0} playlist item(s) to remote service named: <b>{1}</b>'
    ).format(count, serviceName)


def iPinPlaylistToRpsFailed(serviceName: str, error: str):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Error pinning to RPS <b>{0}</b>: {1}'
    ).format(serviceName, error)


def iPinToRps(serviceName):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Pin to remote pinning service: {}'
    ).format(serviceName)


def iUnpinFromRps(serviceName):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Unpin from remote pinning service: {}'
    ).format(serviceName)


def iUnpinFromRpsToolTip(serviceName):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Unpin from remote pinning service: {}'
    ).format(serviceName)


def iPinToRpsWithName(serviceName):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Custom Pin to remote pinning service: {}'
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


def iRpsRegisterHelpMessage():
    return QCoreApplication.translate(
        'GalacteekWindow',
        '''
        <b>
        Register a <b>remote pinning service</b> to keep your
        content available !
        <a href="manual:/pinning.html#remote">Check the manual</a> !
        </b>
        '''
    )


def iRpsStatusSummary(service, status, pinned, pinning, queued, failed):
    return QCoreApplication.translate(
        'GalacteekWindow',
        f'''
        <div>
        <p>Remote pinning service: <b>{service}</b></p>
        <p>{status}</p>
        <ul>
            <li><b>PINNED: {pinned} objects</b></li>
            <li><b>PINNING: {pinning} objects</b></li>
            <li><b>INQUEUE: {queued} objects</b></li>
            <li><b>FAIL: {failed} objects</b></li>
        </ul>
        </div>
        '''
    ).format(service, status, pinned, pinning, queued, failed)


def iRemotePinning():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Remote Pinning'
    )


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
