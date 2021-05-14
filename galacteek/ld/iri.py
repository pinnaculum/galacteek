from galacteek.core import uid4


def superUrn(*args):
    s = ':'.join(args)
    return f'urn:{s}'


def uuidUrn():
    return f'urn:uuid:{uid4()}'


def objectRandomIri(oclass):
    return f'i:/{oclass}/{uid4()}'
