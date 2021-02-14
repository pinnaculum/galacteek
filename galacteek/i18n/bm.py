from PyQt5.QtCore import QCoreApplication


def iBitMessage():
    return QCoreApplication.translate(
        'Galacteek',
        'BitMessage'
    )


def iBitMessagePowCalculated():
    return QCoreApplication.translate(
        'Galacteek',
        'The proof-of-work for your BitMessage was '
        'succesfully calculated'
    )


def iBitMessageAcceptedMessage(bmAddress):
    return QCoreApplication.translate(
        'Galacteek',
        'A message was accepted from: {}'
    ).format(bmAddress)


def iBitMessageReceivedMessage():
    return QCoreApplication.translate(
        'Galacteek',
        'You just received a new message via BitMessage'
    )
