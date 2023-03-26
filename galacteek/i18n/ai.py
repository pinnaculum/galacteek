from PyQt5.QtCore import QCoreApplication


def iOpenAI():
    return QCoreApplication.translate(
        'Galacteek',
        'OpenAI'
    )


def iChatBotDiscussion():
    return QCoreApplication.translate(
        'Galacteek',
        'ChatBot discussion'
    )


def iChatBotGenerateImageCount(count: int):
    return QCoreApplication.translate(
        'Galacteek',
        'Generate {0} image(s)'
    ).format(count)


def iChatBotTranslateToLang(langName: str):
    return QCoreApplication.translate(
        'Galacteek',
        'Translate to: {0}'
    ).format(langName)


def iChatBotInvalidResponse():
    return QCoreApplication.translate(
        'Galacteek',
        'Invalid response from chatbot'
    )
