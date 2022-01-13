from urnparse import URN8141
from urnparse import InvalidURNFormatError

from galacteek.core import uid4


def superUrn(*args):
    s = ':'.join(args)
    return f'urn:{s}'


def uuidUrn():
    return f'urn:uuid:{uid4()}'


def objectRandomIri(oclass):
    return f'i:/{oclass}/{uid4()}'


def urnParse(urn: str):
    try:
        return URN8141.from_string(urn)
    except InvalidURNFormatError:
        return None


def urnStripRqf(urn: str):
    u = urnParse(urn)

    if u:
        return urnParse(
            f'urn:{u.namespace_id}:{u.specific_string}'
        )
