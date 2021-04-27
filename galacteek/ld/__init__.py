from yarl import URL

from galacteek.core import pkgResourcesRscFilename

gLdBaseUri = 'ips://galacteek.ld/'


def ipsContextUri(contextName):
    return f'ips://galacteek.ld/{contextName}'


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
