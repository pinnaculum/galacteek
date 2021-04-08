from galacteek.core import pkgResourcesRscFilename

ldBaseUri = 'ips://galacteek.ld/'


def ipsContextUri(contextName):
    return f'ips://galacteek.ld/{contextName}'


def ldContextsRootPath():
    return pkgResourcesRscFilename('galacteek.ld', 'contexts')


def ldRenderersRootPath():
    return pkgResourcesRscFilename('galacteek.ld', 'renderers')
