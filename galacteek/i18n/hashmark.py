from PyQt5.QtCore import QCoreApplication

from .misc import iUnknown


def iNoTitle():
    return QCoreApplication.translate('GalacteekWindow', 'No title')


def iNoCategory():
    return QCoreApplication.translate('GalacteekWindow', 'No category')


def iNoDescription():
    return QCoreApplication.translate('GalacteekWindow', 'No description')


def iHashmark():
    return QCoreApplication.translate('GalacteekWindow', 'Hashmark')


def iAddHashmark():
    return QCoreApplication.translate('GalacteekWindow', 'Add hashmark')


def iEditHashmark():
    return QCoreApplication.translate('GalacteekWindow', 'Edit hashmark')


def iHashmarkSources():
    return QCoreApplication.translate('GalacteekWindow', 'Hashmark sources')


def iHashmarkSourceAlreadyRegistered():
    return QCoreApplication.translate(
        'GalacteekWindow', 'This hashmarks source is already registered')


def iHashmarkSourcesDbSync():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Synchronize database'
    )


def iHashmarkSourcesAddGitRepo():
    return QCoreApplication.translate(
        'GalacteekWindow', 'Add hashmarks repository source (Git)')


def iHashmarkSourcesAddLegacyIpfsMarks():
    return QCoreApplication.translate(
        'GalacteekWindow', 'Add ipfsmarks source (old format)')


def iHashmarkThisPage():
    return QCoreApplication.translate('GalacteekWindow', 'Hashmark this page')


def iHashmarkRootObject():
    return QCoreApplication.translate(
        'GalacteekWindow', 'Hashmark root object')


def iHashmarks():
    return QCoreApplication.translate('GalacteekWindow', 'Hashmarks')


def iLocalHashmarks():
    return QCoreApplication.translate('GalacteekWindow', 'Local hashmarks')


def iSharedHashmarks():
    return QCoreApplication.translate('GalacteekWindow', 'Shared hashmarks')


def iSearchHashmarks():
    return QCoreApplication.translate('GalacteekWindow', 'Search hashmarks')


def iSearchHashmarksAllAcross():
    return QCoreApplication.translate(
        'GalacteekWindow',
        '''
        <div>
            <p>Search the hashmarks database</p>

            <p>Search by tags using #mytag or @Planet#mytag</p>

            <ul>
                <li><b>@Earth#ipfs</b></li>
                <li>#dapp</li>
                <li>#icon</li>
            </ul>

            <p>Press <b>Shift + Return</b> to validate your search</p>
        </div>
        ''')


def iHashmarksManager():
    return QCoreApplication.translate('GalacteekWindow', 'Hashmarks manager')


def iHashmarkInfoToolTipShort(mark):
    return QCoreApplication.translate(
        'GalacteekWindow',
        '''
            <img src=':/share/icons/hashmarks.png' width='16' height='16' />
            <p>Title: <b>{0}</b></p>
            <p>Description: <b>{1}</b></p>
        ''').format(mark.title if mark.title else iNoTitle(),
                    mark.description if mark.description else iNoDescription(),
                    )


def iHashmarkInfoToolTip(mark):
    return QCoreApplication.translate(
        'GalacteekWindow',
        '''
            <img src=':/share/icons/hashmarks.png' width='16' height='16' />
            <p style='font: Courier 12pt'>{0}</p>

            <p>Title: <b>{1}</b></p>
            <p>Description: <b>{2}</b></p>

            <p>Creation date: <b>{3}</b></p>

            <p>Hashmark source: {4}</p>
        ''').format(mark.uri,
                    mark.title if mark.title else iNoTitle(),
                    mark.description if mark.description else iNoDescription(),
                    mark.datecreated,
                    str(mark.source) if mark.source else iUnknown()
                    )


def iHashmarksLibraryCountAvailable(count):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Hashmarks library: {0} hashmarks available'
    ).format(count)


def iHashmarksLibrary():
    return QCoreApplication.translate('GalacteekWindow',
                                      '''
            <img src=':/share/icons/hashmarks-library.png'
                width='32' height='32' />

            <p>Hashmarks library</p>
        ''')


def iLocalHashmarksCount(count):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Local hashmarks: {0} hashmarks available'
    ).format(count)


def iHashmarksDatabase():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Hashmarks database'
    )
