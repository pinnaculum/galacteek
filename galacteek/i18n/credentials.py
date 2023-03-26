from PyQt5.QtCore import QCoreApplication


def iPasswordsVaultUnlock():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Unlock passwords vault'
    )


def iPasswordsVaultUnlocked():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Passwords vault is unlocked and active'
    )


def iPasswordsVaultCreate():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Create passwords vault'
    )


def iPasswordsVaultOpened():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Passwords vault opened'
    )


def iPasswordsVaultOpenFailed():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Passwords vault could not be opened (wrong password ?)'
    )
