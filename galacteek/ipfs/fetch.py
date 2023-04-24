from yarl import URL

import random

from galacteek import log
from galacteek.config import cGet
from galacteek.core.asynclib import loopTime
from galacteek.core.asynclib.fetch import httpFetch
from galacteek.ipfs.cidhelpers import IPFSPath


def pickGateway(network='main', skim=5):
    """
    Pick an http gateway randomly from the list of declared gateways
    in the config. Returns the URL of the gateway.

    :rtype: URL
    """

    cfg = cGet(f'ipfsHttpGateways.networks.{network}',
               mod='galacteek.ipfs')

    if not cfg:
        return None

    def gfilter(gitem):
        # Sort filter, returns the priority as an integer
        try:
            host, gwcfg = gitem
            return gwcfg.priority
        except Exception:
            return 100

    gws = sorted(cfg.items(), key=gfilter)
    chosenOne = random.choice(gws[0:skim])

    if isinstance(chosenOne, tuple):
        gwhost, gwc = chosenOne

        url = gwc.get('url', f'https://{gwhost}')
        log.debug(f'pickGateway({network}): chosen one is: {url}')

        return URL(url)


async def checkGateway(gatewayUrl: URL,
                       timeout: int = 7) -> tuple:
    """
    Check if an HTTP gateway is responding

    :param URL gatewayUrl: base gateway URL
    :rtype: bool
    """

    iPath = IPFSPath(
        'bafybeifx7yeb55armcsxwwitkymga5xf53dxiarykms3ygqic223w5sk3m'
    )

    start = loopTime()
    path, csum = await httpFetch(
        gatewayUrl.with_path(iPath.objPath),
        timeout=timeout,
        impatient=True
    )
    took = loopTime() - start

    if path and csum:
        path.unlink()

        return True, took

    return False, took


async def fetchWithMyPinataGateway(iPath: IPFSPath,
                                   name: str = 'galacteek',
                                   maxSize=0):
    """
    Fetch an IPFS object with a dedicated pinata gateway
    """
    return await httpFetch(
        URL(f'https://{name}.mypinata.cloud').with_path(iPath.objPath),
        maxSize=maxSize, impatient=True
    )


async def fetchWithSpecificGateway(iPath: IPFSPath,
                                   gwHost: str = 'gateway.pinata.cloud',
                                   maxSize=0):
    """
    Fetch an IPFS object with a certain HTTP gateway
    """
    return await httpFetch(
        URL(f'https://{gwHost}').with_path(iPath.objPath),
        maxSize=maxSize, impatient=True
    )


async def fetchWithRandomGateway(iPath: IPFSPath,
                                 network='main',
                                 maxSize=0):
    """
    Fetch an IPFS object with a random HTTP gateway
    """

    gatewayUrl = pickGateway(network=network)

    if not gatewayUrl:
        log.info(f'Cannot find a suitable gateway for network {network}')
        return

    return await httpFetch(
        gatewayUrl.with_path(iPath.objPath),
        maxSize=maxSize, impatient=True
    )
