from rdflib import URIRef
from yarl import URL

from galacteek.core import pkgResourcesRscFilename

gLdBaseUri = 'ips://galacteek.ld/'
gLdDefaultContext = {
    '@vocab': 'ips://galacteek.ld/'
}


def ipsContextUri(contextName: str, ips='galacteek.ld'):
    return URIRef(f'ips://{ips}/{contextName}')


def ipsTermUri(name: str, ips='galacteek.ld', fragment=None):
    if fragment:
        return URIRef(f'ips://{ips}/{name}#{fragment}')
    else:
        return URIRef(f'ips://{ips}/{name}')


def uriTermExtract(uri):
    try:
        u = URL(uri)
        assert u.scheme in ['ips', 'ipschema']
        return u.path.lstrip('/')
    except Exception:
        return None


def ldContextsRootPath():
    return pkgResourcesRscFilename('galacteek.ld', 'contexts')


def ldRenderersRootPath():
    return pkgResourcesRscFilename('galacteek.ld', 'renderers')
