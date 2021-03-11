from PyQt5.QtCore import QCoreApplication


def iOpenInTab():
    return QCoreApplication.translate('BrowserTabForm', 'Open link in new tab')


def iOpenHttpInTab():
    return QCoreApplication.translate('BrowserTabForm',
                                      'Open http/https link in new tab')


def iOpenLinkInTab():
    return QCoreApplication.translate('BrowserTabForm',
                                      'Open link in new tab')


def iOpenWith():
    return QCoreApplication.translate('BrowserTabForm', 'Open with')


def iDownload():
    return QCoreApplication.translate('BrowserTabForm', 'Download')


def iSaveContainedWebPage():
    return QCoreApplication.translate(
        'BrowserTabForm', 'Save full webpage to the "Web Pages" folder')


def iPrintWebPageText():
    return QCoreApplication.translate(
        'BrowserTabForm', 'Print (text)')


def iSaveWebPageToPdfFile():
    return QCoreApplication.translate(
        'BrowserTabForm', 'Save webpage to PDF')


def iSaveWebPageToPdfFileError():
    return QCoreApplication.translate(
        'BrowserTabForm', 'Error saving webpage to PDF file')


def iSaveWebPageToPdfFileOk(path):
    return QCoreApplication.translate(
        'BrowserTabForm', 'Saved to PDF file: {0}').format(path)


def iJsConsole():
    return QCoreApplication.translate('BrowserTabForm', 'Javascript console')


def iSaveSelectedText():
    return QCoreApplication.translate(
        'BrowserTabForm', 'Save selected text to IPFS')


def iLinkToQaToolbar():
    return QCoreApplication.translate(
        'BrowserTabForm', 'Link to Quick Access toolbar')


def iFollowIpns():
    return QCoreApplication.translate('BrowserTabForm',
                                      'Follow IPNS resource')


def iEnterIpfsCID():
    return QCoreApplication.translate('BrowserTabForm', 'Enter an IPFS CID')


def iBrowseHomePage():
    return QCoreApplication.translate('BrowserTabForm',
                                      'Go to home page')


def iBrowseIpfsCID():
    return QCoreApplication.translate('BrowserTabForm',
                                      'Browse IPFS resource (CID)')


def iBrowseIpfsMultipleCID():
    return QCoreApplication.translate('BrowserTabForm',
                                      'Browse multiple IPFS resources (CID)')


def iEnterIpfsCIDDialog():
    return QCoreApplication.translate('BrowserTabForm',
                                      'Load IPFS CID dialog')


def iFollowIpnsDialog():
    return QCoreApplication.translate('BrowserTabForm',
                                      'IPNS add feed dialog')


def iBrowseIpnsHash():
    return QCoreApplication.translate('BrowserTabForm',
                                      'Browse IPNS resource from hash/name')


def iBrowseCurrentClipItem():
    return QCoreApplication.translate('BrowserTabForm',
                                      'Browse current clipboard item')


def iEnterIpns():
    return QCoreApplication.translate('BrowserTabForm',
                                      'Enter an IPNS hash/name')


def iEnterIpnsDialog():
    return QCoreApplication.translate('BrowserTabForm',
                                      'Load IPNS key dialog')


def iCreateQaMapping():
    return QCoreApplication.translate('BrowserTabForm',
                                      'Create quick-access mapping')


def iHashmarked(path):
    return QCoreApplication.translate('BrowserTabForm',
                                      'Hashmarked {0}').format(path)


def iHashmarkTitleDialog():
    return QCoreApplication.translate('BrowserTabForm',
                                      'Hashmark title')


def iInvalidUrl(text):
    return QCoreApplication.translate('BrowserTabForm',
                                      'Invalid URL: {0}').format(text)


def iUnsupportedUrl():
    return QCoreApplication.translate('BrowserTabForm',
                                      'Unsupported URL type')


def iInvalidObjectPath(text):
    return QCoreApplication.translate(
        'BrowserTabForm',
        'Invalid IPFS object path: {0}').format(text)


def iInvalidCID(text):
    return QCoreApplication.translate(
        'BrowserTabForm',
        '{0} is an invalid IPFS CID (Content IDentifier)').format(text)


def iNotAnIpfsResource():
    return QCoreApplication.translate(
        'BrowserTabForm',
        'This is not an valid IPFS object'
    )


def iWebProfileMinimal():
    return QCoreApplication.translate(
        'BrowserTabForm',
        'Minimal profile')


def iWebProfileIpfs():
    return QCoreApplication.translate(
        'BrowserTabForm',
        'IPFS profile')


def iWebProfileWeb3():
    return QCoreApplication.translate(
        'BrowserTabForm',
        'Web3 profile')


def iCidTooltipMessage(icon, rootCidV, more, rootCid, thisCid):
    return QCoreApplication.translate('BrowserTabForm',
                                      '''
    <p>
      <img src='{0}' width='32' height='32'/>
    </p>

    <p>Root CID: CIDv{1} {2} <b>{3}</b></p>

    <p>This page's CID: <b>{4}</b></p>

    <div style='font-size: 200%;'>
    <p>
      <b>Click on the cube</b> to get a view of the DAG for this page
    </p>
    </div>
''').format(icon, rootCidV, more, rootCid, thisCid)


def iIpnsTooltipMessage(icon, ipnsKey):
    return QCoreApplication.translate('BrowserTabForm',
                                      '''
        <p>
          <img src='{0}' width='32' height='32'/>
        </p>

        <p>IPNS domain/key <b>{1}</b></p>

        <div style='font-size: 200%;'>
        <p>
          <b>Click on the cube</b> to get a view of the DAG for this page
        </p>
        </div>
    ''').format(icon, ipnsKey)
