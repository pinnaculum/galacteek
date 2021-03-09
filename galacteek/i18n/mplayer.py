from PyQt5.QtCore import QCoreApplication


def iMediaPlayer():
    return QCoreApplication.translate('GalacteekWindow', 'Media Player')


def iMediaPlayerQueue():
    return QCoreApplication.translate(
        'GalacteekWindow', 'Queue in media player')


def iMediaPlayerResourceError():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Media player: Resource error'
    )


def iMediaPlayerUnsupportedFormatError():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Media player: unsupported media format'
    )


def iMediaPlayerNetworkError():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Media player: Network error'
    )
