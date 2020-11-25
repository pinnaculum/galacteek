import asyncio
import logging
from typing import Dict

from galacteek.torrent import algorithms
from galacteek.torrent.models import Peer
from galacteek.torrent.network.peer_tcp_client import PeerTCPClient


__all__= ['PeerTCPServer']


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class PeerTCPServer:
    def __init__(self, our_peer_id: bytes, torrent_managers: Dict[bytes, 'algorithms.TorrentManager']):
        self._our_peer_id = our_peer_id
        self._torrent_managers = torrent_managers

        self._server = None
        self._port = None

    async def _accept(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info('peername')
        peer = Peer(addr[0], addr[1])

        client = PeerTCPClient(self._our_peer_id, peer)

        try:
            info_hash = await client.accept(reader, writer)
            if info_hash not in self._torrent_managers:
                raise ValueError('Unknown info_hash')
        except Exception as e:
            client.close()

            if isinstance(e, asyncio.CancelledError):
                raise
            else:
                logger.debug("%s wasn't accepted because of %r", peer, e)
        else:
            self._torrent_managers[info_hash].accept_client(peer, client)

    PORT_RANGE = range(6881, 6889 + 1)

    async def start(self):
        for port in PeerTCPServer.PORT_RANGE:
            try:
                self._server = await asyncio.start_server(self._accept, port=port)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.debug('exception on starting server on port %s: %r', port, e)
            else:
                self._port = port
                logger.info('server started on port %s', port)
                return
        else:
            logger.warning('failed to start a server')

    @property
    def port(self):
        return self._port

    async def stop(self):
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            logger.info('server stopped')
