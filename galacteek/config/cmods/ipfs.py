import re
import copy

from galacteek.config import cGet
from galacteek.config import cSet
from galacteek.config import configSavePackage
from galacteek.core import utcDatetimeIso
from galacteek import log


cmod = 'galacteek.ipfs'


def ipfsNetworks():
    cfg = cGet('ipfsNetworks', mod=cmod)
    if cfg:
        return cfg.items()


def ipfsNetworkConfig(network):
    return cGet(f'ipfsNetworks.{network}', mod=cmod)


def ipfsNetworkAcceptedCovenants(network):
    return cGet(
        f'ipfsNetworks.{network}.covenantsAcceptedByCid',
        mod=cmod
    ).keys()


def ipfsNetworkAcceptCovenant(network: str, covenantCid: str):
    acc = list(ipfsNetworkAcceptedCovenants(network))

    if covenantCid not in acc:
        cSet(f'ipfsNetworks.{network}.covenantsAcceptedByCid.{covenantCid}', {
            'dateAccepted': utcDatetimeIso()
        }, mod=cmod)
        configSavePackage(cmod)

        return True

    return False


def swarmKeyValid(keylines: list):
    try:
        assert re.search(r'/key/swarm/psk/\d*\.\d*\.\d*/',
                         keylines.pop(0)) is not None
        assert re.search(r'/base16/', keylines.pop(0)) is not None
        assert re.search(r'[a-z0-9]{64}', keylines.pop(0)) is not None
        return True
    except Exception as err:
        log.warning(f'Invalid swarm key: {keylines}: {err}')

        return False


def ipfsNetworkSwarmKey(network):
    cfg = ipfsNetworkConfig(network)

    if not cfg:
        return

    keyraw = cfg.get('swarmKey', None)
    if not isinstance(keyraw, str):
        return

    lines = keyraw.split("\n")

    if lines and swarmKeyValid(copy.copy(lines)) is True:
        return "\n".join(line.strip() for line in lines if len(line) > 0)
