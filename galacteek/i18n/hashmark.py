from PyQt5.QtCore import QCoreApplication


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
        ''').format(
            str(mark['title']) if mark['title'] else iNoTitle(),
            str(mark['descr']) if mark['descr'] else iNoDescription(),
    )


def iHashmarkInfoToolTip(uri,
                         iconSrc,
                         title,
                         description,
                         dateCreated):
    return QCoreApplication.translate(
        'GalacteekWindow',
        '''
            <img src='{0}' width='64' height='64' />
            <p style='font: "Segoe UI" 12pt'>{1}</p>

            <p>Title: <b>{2}</b></p>
            <p>Description: <b>{3}</b></p>

            <p>Creation date: <b>{4}</b></p>
        ''').format(iconSrc,
                    uri,
                    title,
                    description,
                    dateCreated)


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


def iHashmarksDatabaseStillEmpty():
    return QCoreApplication.translate(
        'GalacteekWindow',
        '''

        The hashmarks database is empty at the moment, or you haven't
        subscribed to any tags yet.

        If it's the first time you start galacteek, this is normal,
        please wait for the initial database to be downloaded.
        '''
    )


def iPrivateHashmarks(uri: str):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Private hashmarks database'
    )


def iPublicHashmarks(urnBlock: str):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Public hashmarks database: {0}'
    ).format(urnBlock)


def iHashmarksSearchRoom(urnBlock: str):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Hashmarks search room: {0}'
    ).format(urnBlock)
