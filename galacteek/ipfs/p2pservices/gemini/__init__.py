from pathlib import Path
import os.path
import attr

from galacteek.ipfs import ipfsOp
from galacteek.ipfs.tunnel import P2PListener
from galacteek.ipfs.p2pservices import P2PService
from galacteek import log

from aiogeminipfs.security import TOFUContext
from aiogeminipfs.server import Server
from aiogeminipfs.server.fileserver import create_fileserver
from aiogeminipfs.server.unixfsserver import create_unixfs_server

here = os.path.dirname(__file__)


@attr.s(auto_attribs=True)
class GeminiServiceConfig:
    # Default cert/key paths
    certPath: str = os.path.join(here, 'gem-localhost.crt')
    keyPath: str = os.path.join(here, 'gem-localhost.key')

    # Capsule name (used in the p2p service name)
    capsuleName: str = 'default'

    # IPFS path to serve
    servePath: str = None


class P2PGeminiService(P2PService):
    def __init__(self, config=None):
        self.config = config if config else GeminiServiceConfig()

        super().__init__(
            'gemini',
            listenerClass=GeminiIpfsListener,
            description='Gemini service',
            protocolName=f'gemini/{self.config.capsuleName}',
            protocolVersion='1.0',
            listenRange=('127.0.0.1', range(49512, 49532)),
        )


class GeminiLocalListener(P2PListener):
    @ipfsOp
    async def createServer(self, ipfsop, host='127.0.0.1', portRange=[]):
        for port in portRange:
            try:
                certs = {}
                security = TOFUContext(certs, 'localhost.crt', 'localhost.key')

                s = Server(
                    security,
                    create_fileserver(Path.cwd()),
                    port=port
                )
                server = await s.create_server()

                log.debug('Gemini service (port: {port}): started'.format(
                    port=port))

                self._server = server
                return (host, port)
            except Exception as err:
                log.debug(f'Could not start Gemini service: {err}')
                continue


class GeminiIpfsListener(P2PListener):
    @ipfsOp
    async def createServer(self, ipfsop, host='127.0.0.1', portRange=[]):
        for port in portRange:
            try:
                # TOFU context
                certs = {}
                security = TOFUContext(
                    certs,
                    self.service.config.certPath,
                    self.service.config.keyPath
                )

                # Create gemini service with UnixFS handler
                s = Server(
                    security,
                    create_unixfs_server(
                        ipfsop.client,
                        self.service.config.servePath
                    ),
                    port=port
                )

                self._server = await s.create_server()

                log.debug('Gemini service (port: {port}): started'.format(
                    port=port))

                return (host, port)
            except Exception as err:
                log.debug(
                    f'Could not start Gemini service on port {port}: {err}')
                continue
