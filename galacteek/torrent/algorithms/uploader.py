import asyncio
import itertools
import logging
import random
import time
from typing import List, Iterable, cast

from galacteek.torrent.algorithms.peer_manager import PeerManager
from galacteek.torrent.models import Peer, TorrentInfo
from galacteek.torrent.utils import humanize_size


class Uploader:
    def __init__(self, torrent_info: TorrentInfo, logger: logging.Logger, peer_manager: PeerManager):
        self._download_info = torrent_info.download_info
        self._statistics = self._download_info.session_statistics

        self._logger = logger
        self._peer_manager = peer_manager

    CHOKING_CHANGING_TIME = 10
    UPLOAD_PEER_COUNT = 4

    ITERS_PER_OPTIMISTIC_UNCHOKING = 3
    CONNECTED_RECENTLY_THRESHOLD = 60
    CONNECTED_RECENTLY_COEFF = 3

    def _select_optimistically_unchoked(self, peers: Iterable[Peer]) -> Peer:
        cur_time = time.time()
        connected_recently = []
        remaining_peers = []
        peer_data = self._peer_manager.peer_data
        for peer in peers:
            if cur_time - peer_data[peer].connected_time <= Uploader.CONNECTED_RECENTLY_THRESHOLD:
                connected_recently.append(peer)
            else:
                remaining_peers.append(peer)

        max_index = len(remaining_peers) + Uploader.CONNECTED_RECENTLY_COEFF * len(connected_recently) - 1
        index = random.randint(0, max_index)
        if index < len(remaining_peers):
            return remaining_peers[index]
        return connected_recently[(index - len(remaining_peers)) % len(connected_recently)]

    def get_peer_upload_rate(self, peer: Peer) -> int:
        data = self._peer_manager.peer_data[peer]

        rate = data.client.downloaded  # We owe them for downloading
        if self._download_info.complete:
            rate += data.client.uploaded  # To reach maximal upload speed
        return rate

    async def execute(self):
        prev_unchoked_peers = set()
        optimistically_unchoked = None
        for i in itertools.count():
            peer_data = self._peer_manager.peer_data
            alive_peers = list(sorted(peer_data.keys(), key=self.get_peer_upload_rate, reverse=True))
            cur_unchoked_peers = set()
            interested_count = 0

            if Uploader.UPLOAD_PEER_COUNT:
                if i % Uploader.ITERS_PER_OPTIMISTIC_UNCHOKING == 0:
                    if alive_peers:
                        optimistically_unchoked = self._select_optimistically_unchoked(alive_peers)
                    else:
                        optimistically_unchoked = None

                if optimistically_unchoked is not None and optimistically_unchoked in peer_data:
                    cur_unchoked_peers.add(optimistically_unchoked)
                    if peer_data[optimistically_unchoked].client.peer_interested:
                        interested_count += 1

            for peer in cast(List[Peer], alive_peers):
                if interested_count == Uploader.UPLOAD_PEER_COUNT:
                    break
                if peer_data[peer].client.peer_interested:
                    interested_count += 1

                cur_unchoked_peers.add(peer)

            for peer in prev_unchoked_peers - cur_unchoked_peers:
                if peer in peer_data:
                    peer_data[peer].client.am_choking = True
            for peer in cur_unchoked_peers:
                peer_data[peer].client.am_choking = False
            self._logger.debug('now %s peers are unchoked (total_uploaded = %s)', len(cur_unchoked_peers),
                               humanize_size(self._statistics.total_uploaded))

            await asyncio.sleep(Uploader.CHOKING_CHANGING_TIME)

            prev_unchoked_peers = cur_unchoked_peers
