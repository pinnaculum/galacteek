import asyncio
import copy
import logging
import os
import pickle
import shutil
from typing import Dict, List, Optional

from galacteek.torrent.algorithms import TorrentManager
from galacteek.torrent.models import generate_peer_id, TorrentInfo, TorrentState
from galacteek.torrent.network import PeerTCPServer
from galacteek.torrent.utils import import_signals
from galacteek.core.asynclib import asyncRmTree
from galacteek import log
from galacteek import ensure


QObject, pyqtSignal = import_signals()


__all__ = ['ControlManager']


# state_filename = os.path.expanduser('~/.torrent_gui_state')


logger = log


class ControlManager(QObject):
    if pyqtSignal:
        torrents_suggested = pyqtSignal(list)
        torrent_added = pyqtSignal(TorrentState)
        torrent_changed = pyqtSignal(TorrentState)
        torrent_removed = pyqtSignal(bytes)

    def __init__(self, state_path=None):
        super().__init__()

        self._loop = asyncio.get_event_loop()
        self._statelock = asyncio.Lock()

        self.state_filename = state_path if state_path else \
            os.path.expanduser('~/.torrent_gui_state')

        self._our_peer_id = generate_peer_id()

        self._torrents = {}          # type: Dict[bytes, TorrentInfo]
        self._torrent_managers = {}  # type: Dict[bytes, TorrentManager]

        self._server = PeerTCPServer(self._our_peer_id, self._torrent_managers)

        self._torrent_manager_executors = {}  # type: Dict[bytes, asyncio.Task]
        self._state_updating_executor = None  # type: Optional[asyncio.Task]

        self.last_torrent_dir = None   # type: Optional[str]
        self.last_download_dir = None  # type: Optional[str]

    def get_torrents(self) -> List[TorrentInfo]:
        return list(self._torrents.values())

    async def start(self):
        await self._server.start()

    def _start_torrent_manager(self, torrent_info: TorrentInfo):
        info_hash = torrent_info.download_info.info_hash

        manager = TorrentManager(torrent_info, self._our_peer_id, self._server.port)
        if pyqtSignal:
            manager.state_changed.connect(lambda: self.torrent_changed.emit(TorrentState(torrent_info)))
        self._torrent_managers[info_hash] = manager
        self._torrent_manager_executors[info_hash] = asyncio.ensure_future(manager.run())

    def add(self, torrent_info: TorrentInfo):
        info_hash = torrent_info.download_info.info_hash
        if info_hash in self._torrents:
            raise ValueError('This torrent is already added')

        if not torrent_info.paused:
            self._start_torrent_manager(torrent_info)
        self._torrents[info_hash] = torrent_info

        ensure(self._dump_state())

        if pyqtSignal:
            self.torrent_added.emit(TorrentState(torrent_info))

    def resume(self, info_hash: bytes):
        if info_hash not in self._torrents:
            raise ValueError('Torrent not found')
        torrent_info = self._torrents[info_hash]
        if not torrent_info.paused:
            raise ValueError('The torrent is already running')

        self._start_torrent_manager(torrent_info)

        torrent_info.paused = False

        if pyqtSignal:
            self.torrent_changed.emit(TorrentState(torrent_info))

    async def _stop_torrent_manager(self, info_hash: bytes):
        manager_executor = self._torrent_manager_executors[info_hash]
        manager_executor.cancel()
        if 0:
            try:
                await manager_executor
            except asyncio.CancelledError:
                pass
        del self._torrent_manager_executors[info_hash]

        manager = self._torrent_managers[info_hash]
        del self._torrent_managers[info_hash]
        await manager.stop()

    async def remove(self, info_hash: bytes, purgeFiles=False):
        if info_hash not in self._torrents:
            raise ValueError('Torrent not found')
        torrent_info = self._torrents[info_hash]

        log.debug(f'Remove torrent {info_hash} downloaded in '
                  f'{torrent_info.download_dir}')

        del self._torrents[info_hash]
        if not torrent_info.paused:
            await self._stop_torrent_manager(info_hash)

        if purgeFiles:
            log.debug(f'Purging torrent directory: '
                      f'{torrent_info.download_dir}')
            await asyncRmTree(torrent_info.download_dir)

        await self._dump_state()
        log.debug(f'Removed torrent {info_hash}')

        if pyqtSignal:
            self.torrent_removed.emit(info_hash)

    async def pause(self, info_hash: bytes):
        if info_hash not in self._torrents:
            raise ValueError('Torrent not found')
        torrent_info = self._torrents[info_hash]
        if torrent_info.paused:
            raise ValueError('The torrent is already paused')

        await self._stop_torrent_manager(info_hash)

        torrent_info.paused = True

        if pyqtSignal:
            self.torrent_changed.emit(TorrentState(torrent_info))

    async def _dump_state(self):
        async with self._statelock:
            torrent_list = []
            for manager, torrent_info in self._torrents.items():
                torrent_info = copy.copy(torrent_info)
                torrent_info.download_info = copy.copy(torrent_info.download_info)
                torrent_info.download_info.reset_run_state()
                torrent_list.append(torrent_info)

            try:
                with open(self.state_filename, 'wb') as f:
                    pickle.dump((self.last_torrent_dir, self.last_download_dir, torrent_list), f)

                logger.debug(f'State: saved {len(torrent_list)} torrents')
            except Exception as err:
                logger.warning(f'Failed to save state: {err}')

    STATE_UPDATE_INTERVAL = 5 * 60

    async def _execute_state_updates(self):
        while True:
            await asyncio.sleep(ControlManager.STATE_UPDATE_INTERVAL)

            await self._dump_state()

    def invoke_state_dumps(self):
        self._state_updating_executor = asyncio.ensure_future(self._execute_state_updates())

    def load_state(self):
        if not os.path.isfile(self.state_filename):
            return

        with open(self.state_filename, 'rb') as f:
            self.last_torrent_dir, self.last_download_dir, torrent_list = pickle.load(f)

        for torrent_info in torrent_list:
            self.add(torrent_info)

        logger.debug(f'State: recovered ({len(torrent_list)} torrents)')

    async def stop(self):
        await self._server.stop()

        tasks = list(self._torrent_manager_executors.values())
        if self._state_updating_executor is not None:
            tasks.append(self._state_updating_executor)

        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.wait(tasks)

        if self._torrent_managers:
            await asyncio.wait([manager.stop() for manager in self._torrent_managers.values()])

        if self._state_updating_executor is not None:  # Only if we have loaded starting state
            await self._dump_state()
