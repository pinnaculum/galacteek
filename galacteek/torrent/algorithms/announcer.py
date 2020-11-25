import asyncio
import logging
from typing import Optional

from galacteek.torrent.algorithms.peer_manager import PeerManager
from galacteek.torrent.models import TorrentInfo
from galacteek.torrent.network import BaseTrackerClient, EventType, create_tracker_client


class Announcer:
    def __init__(self, torrent_info: TorrentInfo, our_peer_id: bytes, server_port: int, logger: logging.Logger,
                 peer_manager: PeerManager):
        self._torrent_info = torrent_info
        self._download_info = torrent_info.download_info
        self._our_peer_id = our_peer_id
        self._server_port = server_port

        self._logger = logger
        self._peer_manager = peer_manager

        self._last_tracker_client = None
        self._more_peers_requested = asyncio.Event()
        self._task = None  # type: Optional[asyncio.Task]

    @property
    def last_tracker_client(self) -> BaseTrackerClient:
        return self._last_tracker_client

    @property
    def more_peers_requested(self) -> asyncio.Event:
        return self._more_peers_requested

    FAKE_SERVER_PORT = 6881
    DEFAULT_MIN_INTERVAL = 90

    async def try_to_announce(self, event: EventType) -> bool:
        server_port = self._server_port if self._server_port is not None else Announcer.FAKE_SERVER_PORT

        tier = None
        url = None
        lift_url = False
        try:
            for tier in self._torrent_info.announce_list:
                for url in tier:
                    try:
                        client = create_tracker_client(url, self._download_info, self._our_peer_id)
                        await client.announce(server_port, event)
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        self._logger.info('announce to "%s" failed: %r', url, e)
                    else:
                        peer_count = len(client.peers) if client.peers else 'no'
                        self._logger.debug('announce to "%s" succeed (%s peers, interval = %s, min_interval = %s)',
                                           url, peer_count, client.interval, client.min_interval)

                        self._last_tracker_client = client
                        lift_url = True
                        return True
            return False
        finally:
            if lift_url:
                tier.remove(url)
                tier.insert(0, url)

    async def execute(self):
        try:
            while True:
                if self._last_tracker_client.min_interval is not None:
                    min_interval = self._last_tracker_client.min_interval
                else:
                    min_interval = min(Announcer.DEFAULT_MIN_INTERVAL, self._last_tracker_client.interval)
                await asyncio.sleep(min_interval)

                default_interval = self._last_tracker_client.interval
                try:
                    await asyncio.wait_for(self._more_peers_requested.wait(), default_interval - min_interval)
                    more_peers = True
                    self._more_peers_requested.clear()
                except asyncio.TimeoutError:
                    more_peers = False

                await self.try_to_announce(EventType.none)
                # TODO: if more_peers, maybe rerequest in case of exception

                self._peer_manager.connect_to_peers(self._last_tracker_client.peers, more_peers)
        finally:
            await self.try_to_announce(EventType.stopped)
