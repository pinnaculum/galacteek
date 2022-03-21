import aiohttp

from galacteek.ipfs import ipfsOp


class BaseGraphSynchronizer:
    def __init__(self, config=None):
        self.config = config

    @ipfsOp
    async def syncFromRemote(self, ipfsop,
                             peerId: str,
                             iri: str,
                             p2pEndpoint: str,
                             graphDescr=None):
        print('sync from remote', graphDescr)
        creds = graphDescr.get('smartqlCredentials', {})
        auth = aiohttp.BasicAuth(
            creds.get('user', 'smartql'),
            creds.get('password', '')
        )

        async with ipfsop.p2pDialerFromAddr(p2pEndpoint) as dial:
            if dial.failed:
                return False

            return await self.sync(
                ipfsop,
                peerId,
                iri,
                dial,
                auth
            )

    async def sync(self, ipfsop,
                   peerId: str,
                   iri: str,
                   dial,
                   auth):
        pass
