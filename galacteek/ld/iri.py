import hashlib
import secrets

from rdflib import URIRef

from urnparse import URN8141
from urnparse import InvalidURNFormatError

from galacteek.core import uid4


def superUrn(*args):
    s = ':'.join(args)
    return URIRef(f'urn:{s}')


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


def ipfsPeerUrn(peerId: str):
    return URIRef(f'urn:ipfs:peer:{peerId}')


def p2pLibrarianGenUrn(peerId: str):
    """
    Generate Librarian ID based on PeerID

    :rtype: URIRef
    """
    h = hashlib.sha3_256()
    h.update(str(peerId).encode())
    h.update(secrets.token_hex(32).encode())

    return URIRef(f'urn:glk:p2plibrarian:{h.hexdigest()}')
