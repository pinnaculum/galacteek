import asyncio
import logging
import time
from typing import Dict, Optional, Sequence

from galacteek.torrent.file_structure import FileStructure
from galacteek.torrent.models import Peer, TorrentInfo
from galacteek.torrent.network import PeerTCPClient


class PeerData:
    DOWNLOAD_REQUEST_QUEUE_SIZE = 150

    def __init__(self, client: PeerTCPClient, client_task: asyncio.Task, connected_time: float):
        self._client = client
        self._client_task = client_task
        self._connected_time = connected_time
        self.hanged_time = None  # type: Optional[float]
        self.queue_size = 0

    @property
    def client(self) -> PeerTCPClient:
        return self._client

    @property
    def client_task(self) -> asyncio.Task:
        return self._client_task

    @property
    def connected_time(self) -> float:
        return self._connected_time

    def is_free(self) -> bool:
        return self.queue_size < PeerData.DOWNLOAD_REQUEST_QUEUE_SIZE

    def is_available(self) -> bool:
        return self.is_free() and not self._client.peer_choking


class PeerManager:
    def __init__(self, torrent_info: TorrentInfo, our_peer_id: bytes,
                 logger: logging.Logger, file_structure: FileStructure):
        # self._torrent_info = torrent_info
        self._download_info = torrent_info.download_info
        self._statistics = self._download_info.session_statistics
        self._our_peer_id = our_peer_id

        self._logger = logger
        self._file_structure = file_structure

        self._peer_data = {}
        self._client_executors = {}          # type: Dict[Peer, asyncio.Task]
        self._keeping_alive_executor = None  # type: Optional[asyncio.Task]
        self._last_connecting_time = None    # type: Optional[float]
        self._shutting_down = False

    @property
    def peer_data(self) -> Dict[Peer, PeerData]:
        return self._peer_data

    @property
    def last_connecting_time(self) -> int:
        return self._last_connecting_time

    async def _execute_peer_client(self, peer: Peer, client: PeerTCPClient, *, need_connect: bool):
        try:
            if need_connect:
                await client.connect(self._download_info, self._file_structure)
            else:
                client.confirm_info_hash(self._download_info, self._file_structure)

            await asyncio.sleep(0.2)

            self._peer_data[peer] = PeerData(client, asyncio.Task.current_task(), time.time())
            self._statistics.peer_count += 1

            await client.run()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._logger.debug('%s disconnected because of %r', peer, e)
        finally:
            if peer in self._peer_data:
                self._statistics.peer_count -= 1
                del self._peer_data[peer]

                for info in self._download_info.pieces:
                    if peer in info.owners:
                        info.owners.remove(peer)
                if peer in self._statistics.peer_last_download:
                    del self._statistics.peer_last_download[peer]
                if peer in self._statistics.peer_last_upload:
                    del self._statistics.peer_last_upload[peer]

            client.close()

            del self._client_executors[peer]

    KEEP_ALIVE_TIMEOUT = 2 * 60

    async def _execute_keeping_alive(self):
        while True:
            await asyncio.sleep(PeerManager.KEEP_ALIVE_TIMEOUT)
            if self._shutting_down:
                return

            self._logger.debug('broadcasting keep-alives to %s alive peers', len(self._peer_data))
            for data in self._peer_data.values():
                data.client.send_keep_alive()

    MAX_PEERS_TO_ACTIVELY_CONNECT = 30
    MAX_PEERS_TO_ACCEPT = 55

    def connect_to_peers(self, peers: Sequence[Peer], force: bool):
        peers = list({peer for peer in peers
                      if peer not in self._client_executors and not self._download_info.is_banned(peer)})
        if force:
            max_peers_count = PeerManager.MAX_PEERS_TO_ACCEPT
        else:
            max_peers_count = PeerManager.MAX_PEERS_TO_ACTIVELY_CONNECT
        peers_to_connect_count = max(max_peers_count - len(self._peer_data), 0)
        self._logger.debug('trying to connect to %s new peers', min(len(peers), peers_to_connect_count))

        for peer in peers[:peers_to_connect_count]:
            client = PeerTCPClient(self._our_peer_id, peer)
            self._client_executors[peer] = asyncio.ensure_future(
                self._execute_peer_client(peer, client, need_connect=True))

        self._last_connecting_time = time.time()

    def accept_client(self, peer: Peer, client: PeerTCPClient):
        if self._shutting_down:
            return
        if len(self._peer_data) > PeerManager.MAX_PEERS_TO_ACCEPT or self._download_info.is_banned(peer) or \
                peer in self._client_executors:
            client.close()
            return
        self._logger.debug('accepted connection from %s', peer)

        self._client_executors[peer] = asyncio.ensure_future(
            self._execute_peer_client(peer, client, need_connect=False))

    def invoke(self):
        self._keeping_alive_executor = asyncio.ensure_future(self._execute_keeping_alive())

    async def stop(self):
        self._shutting_down = True
        tasks = []
        if self._keeping_alive_executor is not None:
            tasks.append(self._keeping_alive_executor)
        tasks += list(self._client_executors.values())

        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.wait(tasks)
