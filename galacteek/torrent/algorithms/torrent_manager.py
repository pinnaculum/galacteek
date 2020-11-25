import asyncio
import logging
import random
from typing import List, Optional

from galacteek.torrent.algorithms.announcer import Announcer
from galacteek.torrent.algorithms.downloader import Downloader
from galacteek.torrent.algorithms.peer_manager import PeerManager
from galacteek.torrent.algorithms.speed_measurer import SpeedMeasurer
from galacteek.torrent.algorithms.uploader import Uploader
from galacteek.torrent.file_structure import FileStructure
from galacteek.torrent.models import Peer, TorrentInfo, DownloadInfo
from galacteek.torrent.network import EventType, PeerTCPClient
from galacteek.torrent.utils import import_signals


QObject, pyqtSignal = import_signals()


__all__ = ['TorrentManager']


class TorrentManager(QObject):
    if pyqtSignal:
        state_changed = pyqtSignal()

    LOGGER_LEVEL = logging.DEBUG
    SHORT_NAME_LEN = 19

    def __init__(self, torrent_info: TorrentInfo, our_peer_id: bytes, server_port: Optional[int]):
        super().__init__()

        self._torrent_info = torrent_info
        download_info = torrent_info.download_info  # type: DownloadInfo
        download_info.reset_run_state()
        download_info.reset_stats()

        short_name = download_info.suggested_name
        if len(short_name) > TorrentManager.SHORT_NAME_LEN:
            short_name = short_name[:TorrentManager.SHORT_NAME_LEN] + '..'
        self._logger = logging.getLogger('"{}"'.format(short_name))
        self._logger.setLevel(TorrentManager.LOGGER_LEVEL)

        self._executors = []  # type: List[asyncio.Task]

        self._file_structure = FileStructure(torrent_info.download_dir, torrent_info.download_info)

        self._peer_manager = PeerManager(torrent_info, our_peer_id, self._logger, self._file_structure)
        self._announcer = Announcer(torrent_info, our_peer_id, server_port, self._logger, self._peer_manager)
        self._downloader = Downloader(torrent_info, our_peer_id, self._logger, self._file_structure,
                                      self._peer_manager, self._announcer)
        self._uploader = Uploader(torrent_info, self._logger, self._peer_manager)
        self._speed_measurer = SpeedMeasurer(torrent_info.download_info.session_statistics)
        if pyqtSignal:
            self._downloader.progress.connect(self.state_changed)
            self._speed_measurer.updated.connect(self.state_changed)

    ANNOUNCE_FAILED_SLEEP_TIME = 3

    def _shuffle_announce_tiers(self):
        for tier in self._torrent_info.announce_list:
            random.shuffle(tier)

    async def run(self):
        # await self._file_structure.initialize()

        self._shuffle_announce_tiers()
        while not await self._announcer.try_to_announce(EventType.started):
            await asyncio.sleep(TorrentManager.ANNOUNCE_FAILED_SLEEP_TIME)

        self._peer_manager.connect_to_peers(self._announcer.last_tracker_client.peers, True)

        self._executors += [asyncio.ensure_future(coro) for coro in [
            self._announcer.execute(),
            self._uploader.execute(),
            self._speed_measurer.execute(),
        ]]

        self._peer_manager.invoke()
        await self._downloader.run()

    def accept_client(self, peer: Peer, client: PeerTCPClient):
        self._peer_manager.accept_client(peer, client)

    async def stop(self):
        await self._downloader.stop()
        await self._peer_manager.stop()

        executors = [task for task in self._executors if task is not None]
        for task in reversed(executors):
            task.cancel()
        if executors:
            await asyncio.wait(executors)

        self._file_structure.close()
