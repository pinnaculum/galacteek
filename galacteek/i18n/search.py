from PyQt5.QtCore import QCoreApplication


def iSearchIpfsContent():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Search content on IPFS (ipfs-search/cyber)'
    )


def iSearchUseShiftReturn():
    return QCoreApplication.translate(
        'GalacteekWindow',
        '<p>Press <b>Shift + Return</b> to run a search</p>')


def iIpfsSearchText(text):
    return QCoreApplication.translate('GalacteekWindow',
                                      'Search: {0}').format(text)


def iIpfsSearch():
    return QCoreApplication.translate('GalacteekWindow',
                                      'IPFS Search')


def iSearch():
    return QCoreApplication.translate('GalacteekWindow',
                                      'Search')
