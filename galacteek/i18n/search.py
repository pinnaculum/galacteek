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


def iKgSearchForTags(langTag: str):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Search for tags in lang: {0}'
    ).format(langTag)


def iKgSearching(text: str, platform: str):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Searching <b>{0}</b> on knowledge platform <b>{1}</b>'
    ).format(text, platform)


def iKgSearchNoResultsFor(text: str, msg: str):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'No results for <b>{0}</b>: {1}'
    ).format(text, msg)


def iKgSearchBePatient0():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'The search query can take a while, please be patient !'
    )


def iKgSearchBePatient1():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Your patience will be rewarded !'
    )


def iKgSearchBePatient2():
    return QCoreApplication.translate(
        'GalacteekWindow',
        "Your patience hasn't been rewarded yet"
    )


def iKgSearchBePatient3():
    return QCoreApplication.translate(
        'GalacteekWindow',
        "Not much hope for any results now, but hang in there"
    )
