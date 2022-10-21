from galacteek.config import cGet


def defaultContentLangTag():
    return cGet('defaultContentLanguage',
                mod='galacteek.application')
