from galacteek.config import cGet
from galacteek.config import cSet
from galacteek.config import configSavePackage
from galacteek.config import merge


cmod = 'galacteek.ipfs.pinning'
rSrvsKey = 'remotePinning.services'
defCfgKey = 'remotePinning.defaultServiceConfig'


def remoteServices():
    return cGet(rSrvsKey, mod=cmod)


def rpsList():
    return remoteServices()


def rpsCount():
    return len(rpsList())


def remoteServiceExistsByName(name: str):
    for srv in remoteServices():
        if srv.serviceName == name:
            return True

    return False


def rpsByDisplayName(name: str):
    for srv in remoteServices():
        if srv.displayName == name:
            return srv


def rpsByServiceName(name: str):
    for srv in remoteServices():
        if srv.serviceName == name:
            return srv


def rpsExists(rService, services=None):
    """
    Checks if we already have this service in the config
    """
    name = rService['Service']

    for srv in remoteServices():
        if srv.serviceName == name:
            return True

    return False


def configSave():
    configSavePackage(cmod)


def rpsConfigGetByServiceName(serviceName: str):
    default = cGet(defCfgKey, mod=cmod)

    for srv in remoteServices():
        if srv.serviceName == serviceName:
            return merge(default, srv)


def rpsConfigRemove(displayName: str):
    """
    Remove a RPS from the config, filtering by display name

    There must be a better way of doing this ..
    """

    services = list(remoteServices().copy())
    removed = False

    for idx, srv in enumerate(services):
        if srv.displayName == displayName:
            # pop him off
            services.pop(idx)
            removed = True

            # Can't have two with the same display name normally
            break

    if removed:
        cSet(rSrvsKey, services, mod=cmod)

    return removed


def rpsConfigRegister(rService: dict, peerId: str):
    """
    Register a remote pinning service in the config

    rService is an entry in the 'RemoteServices' list
    returned by IPFS

    peerID is the peer ID of the node that has this service
    """

    from galacteek.config import merge

    name = rService['Service']
    services = remoteServices()

    if rpsExists(rService, services=services):
        return False

    default = cGet(defCfgKey, mod=cmod)

    # Append
    cfg = {
        'displayName': name,
        'serviceName': name,
        'endpoint': rService['ApiEndpoint'],
        'peerId': peerId,
        'priority': 0,
        'pinQueueName': name,
        'default': False,
        'enabled': True,
        'iconCid': None
    }

    merged = merge(default, cfg)
    services.append(merged)

    # Patch
    cSet(rSrvsKey, services, mod=cmod)

    # Profit
    return True
