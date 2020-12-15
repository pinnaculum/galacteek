from galacteek import log
# from galacteek.config import configPackageMerge
from galacteek.config import regConfigFromPyPkg


cfgInitTable = {
    'galacteek.services.bitmessage': None,
    'galacteek.services.tor': None,
    'galacteek.blockchain.ethereum': None
}


def initFromTable():
    for pkg, dst in cfgInitTable.items():
        log.debug(f'Config: initializing from package/module {pkg}')

        regConfigFromPyPkg(pkg)

    return True
