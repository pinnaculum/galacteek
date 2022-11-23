import re
from urllib.parse import parse_qs
from urllib.parse import quote

from rdflib import URIRef
from yarl import URL

from galacteek.core import normalizedUtcDate

"""
Decentralized Identifiers (DIDs) implementation
"""


didIdentRe = re.compile(
    r'(?P<scheme>(did))' +
    r'\:(?P<method>([\w]+))\:(?P<id>([\w])+)'
)


didRe = re.compile(
    r'(?P<scheme>(did))' +
    r'\:(?P<method>([\w]+))\:(?P<id>([\w])+)' +
    r'(?P<params>([\w=:;]+)?)' +
    r'(?P<path>([\w=/_\-()\.\:\s]+)?)' +
    r'(?P<query>(\?[\w=/_\-&]+)?)' +
    r'#?(?P<fragment>([\w]+)?)$'
)


ipidIdentRe = re.compile(
    r'(?P<scheme>(did))\:(?P<method>(ipid))\:(?P<id>([\w]){46,59})$'
)


def normedUtcDate():
    return normalizedUtcDate()


def serviceIdToUrl(didUri: str, quotep=False) -> URL:
    """
    Transform a DID service URI string to a ipid://<did>/<path> URL

    :param str didUrl: DID service uri
    :rtype: URL
    """
    m = didRe.match(didUri)

    if m and m.group('method') == 'ipid':
        path = m.group('path')

        return URL.build(
            scheme=m.group('method'),
            host=m.group('id'),
            path=quote(path) if quotep else path
        )


def serviceIdToUriRef(didUrl: str) -> URIRef:
    url = serviceIdToUrl(didUrl)

    return URIRef(str(url)) if url else None


def didExplode(did: str) -> dict:
    """
    Explode a DID into its different components.

    Returns None if invalid, or a dictionary with
    the following keys if the DID is valid:

        - scheme: the DID scheme (should be 'did')
        - method: the DID method ('btc', 'ipid', ...)
        - id: the DID method-specific id
        - params: the list of params, as a dictionary
        - fragment: fragment (returned without '#')
        - query: DID query, as a dictionary

    :param str did: The DID string to analyze
    :rtype: dict
    """

    match = didRe.match(did)
    if match:
        return {
            'scheme': match.group('scheme'),
            'method': match.group('method'),
            'id': match.group('id'),
            'path': match.group('path'),
            'params': parse_qs(match.group('params')),
            'query': parse_qs(match.group('query').lstrip('?')),
            'fragment': match.group('fragment')
        }
