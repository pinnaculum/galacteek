from PyQt5.QtCore import QCoreApplication


def iLanguageChanged():
    return QCoreApplication.translate(
        'Galacteek',
        "The application's language was changed"
    )


def iLangEnglish():
    return QCoreApplication.translate('Galacteek', 'English')


def iLangFrench():
    return QCoreApplication.translate('Galacteek', 'French')


def iLangCastilianSpanish():
    return QCoreApplication.translate('Galacteek', 'Spanish (Castilian)')
