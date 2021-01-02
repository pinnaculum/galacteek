from galacteek import log
from galacteek.config import regConfigFromPyPkg


cfgInitTable = {
    'galacteek.services.bitmessage': None,
    'galacteek.services.tor': None,
    'galacteek.services.ethereum': None,
    # 'galacteek.blockchain.ethereum': None
}


def initFromTable():
    for pkg, dst in cfgInitTable.items():
        log.debug(f'Config: initializing from package/module {pkg}')

        try:
            regConfigFromPyPkg(pkg)
        except Exception:
            log.debug(f'Failed to load config from package: {pkg}')
            continue

    return True
