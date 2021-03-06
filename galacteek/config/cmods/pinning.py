from galacteek.config import cGet
from galacteek.config import cSet
from galacteek.config import configSavePackage


cmod = 'galacteek.ipfs.pinning'
rSrvsKey = 'remotePinning.services'


def remoteServices():
    return cGet(rSrvsKey, mod=cmod)


def rpsList():
    return remoteServices()


def remoteServiceExistsByName(name: str):
    for srv in remoteServices():
        if srv.serviceName == name:
            return True

    return False


def rpsByDisplayName(name: str):
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


def rpsConfigRemove(serviceName: str):
    pass


def rpsConfigRegister(rService: dict, peerId: str):
    """
    Register a remote pinning service in the config

    rService is an entry in the 'RemoteServices' list
    returned by IPFS

    peerID is the peer ID of the node that has this service
    """

    name = rService['Service']
    services = remoteServices()

    if rpsExists(rService, services=services):
        return False

    # Append
    services.append({
        'displayName': name,
        'serviceName': name,
        'endpoint': rService['ApiEndpoint'],
        'peerId': peerId,
        'priority': 100,
        'pinQueueName': name,
        'iconCid': None
    })

    # Patch
    cSet(rSrvsKey, services, mod=cmod)

    # Profit
    return True
