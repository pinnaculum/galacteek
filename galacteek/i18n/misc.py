from PyQt5.QtCore import QCoreApplication


def iThemes():
    return QCoreApplication.translate(
        'Galacteek',
        'Themes'
    )


def iUnknown():
    return QCoreApplication.translate('GalacteekWindow', 'Unknown')


def iUnknownAgent():
    return QCoreApplication.translate('GalacteekWindow', 'Unknown agent')


def iNewReleaseAvailable():
    return QCoreApplication.translate(
        'Galacteek',
        'New release available: upgrade with pip install -U galacteek')


def iYes():
    return QCoreApplication.translate('Galacteek', 'yes')


def iNo():
    return QCoreApplication.translate('Galacteek', 'no')


def iDonate():
    return QCoreApplication.translate('Galacteek', 'Donate')


def iDonateBitcoin():
    return QCoreApplication.translate('Galacteek', 'Donate with Bitcoin')


def iDonateLiberaPay():
    return QCoreApplication.translate('Galacteek', 'Donate with LiberaPay')


def iDonateKoFi():
    return QCoreApplication.translate('Galacteek', 'Donate with Ko-Fi')


def iDonateGithubSponsors():
    return QCoreApplication.translate(
        'Galacteek', 'Donate with Github Sponsors')
