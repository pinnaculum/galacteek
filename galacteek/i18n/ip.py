from PyQt5.QtCore import QCoreApplication


# IP Tags


def iIPTag():
    return QCoreApplication.translate('GalacteekWindow', 'IPTag')


def iIPTagLong():
    return QCoreApplication.translate(
        'GalacteekWindow', 'InterPlanetary tag')


def iIPTagInvalid():
    return QCoreApplication.translate('GalacteekWindow', 'Invalid tag')


def iIPTagFetchingMeaning(name: str):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Searching a description for <b>{0}</b> ...'
    ).format(name)


def iIPTagFetchMeaningError(err: str):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Error finding the meaning of the tag: {0}'
    ).format(err)


def iHashmarkIPTagsEdit():
    return QCoreApplication.translate(
        'GalacteekWindow', 'Edit hashmark IP tags')


# Space jargon


def iIPHandle():
    return QCoreApplication.translate(
        'GalacteekWindow', 'IP handle')


def iConstellation():
    return QCoreApplication.translate(
        'GalacteekWindow', 'Constellation')


def iVirtualPlanet():
    return QCoreApplication.translate(
        'GalacteekWindow', 'Virtual Planet')
