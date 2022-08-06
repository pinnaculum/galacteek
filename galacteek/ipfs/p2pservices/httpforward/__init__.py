import attr
from multiaddr.multiaddr import Multiaddr

from galacteek.ipfs.tunnel import P2PListener
from galacteek.ipfs.p2pservices import P2PService


@attr.s(auto_attribs=True)
class HttpForwardServiceConfig:
    host: str = '127.0.0.1'
    port: int = 8080
    advertisePort: int = 80

    # The multiaddr of the HTTP service we forward to
    targetMultiAddr: str = '/ip4/127.0.0.1/tcp/8080'


class P2PHttpForwardService(P2PService):
    def __init__(self, config=None):
        self.config = config if config else HttpForwardServiceConfig()

        super().__init__(
            'ipfs-http',
            listenerClass=HttpForwardListener,
            description='HTTP forward service',
            protocolName=f'ipfs-http/{self.config.advertisePort}',
            protocolVersion='1.0',
            listenRange=('127.0.0.1', range(8080, 9080)),
        )


class HttpForwardListener(P2PListener):
    async def createServer(self, host='127.0.0.1', portRange=[]):
        # We just forward to the given multiaddr
        # TODO: do not fake createServer, change P2PListener's API

        return Multiaddr(self.service.config.targetMultiAddr)
