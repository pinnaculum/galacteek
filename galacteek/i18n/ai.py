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


def iChatBotGenerateOneImage():
    return QCoreApplication.translate(
        'Galacteek',
        'Generate an image'
    )


def iChatBotGenerateImageCount(count: int):
    return QCoreApplication.translate(
        'Galacteek',
        'Generate {0} images'
    ).format(count)


def iChatBotImageVariation():
    return QCoreApplication.translate(
        'Galacteek',
        'Image variation'
    )


def iChatBotCreateImageVariation(count: int):
    return QCoreApplication.translate(
        'Galacteek',
        'Create {0} image variation(s)'
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
