import asyncio
import hashlib
import logging
import random
import time
from collections import deque, OrderedDict
from math import ceil
from typing import List, Optional, Tuple, Iterator

from galacteek.ipfs import ipfsOp
from galacteek import log as glklog

from galacteek.torrent.algorithms.announcer import Announcer
from galacteek.torrent.algorithms.peer_manager import PeerData, PeerManager
from galacteek.torrent.file_structure import FileStructure
from galacteek.torrent.models import BlockRequestFuture, Peer, TorrentInfo, TorrentState
from galacteek.torrent.network import EventType
from galacteek.torrent.utils import floor_to, import_signals


QObject, pyqtSignal = import_signals()


class NotEnoughPeersError(RuntimeError):
    pass


class NoRequestsError(RuntimeError):
    pass


class Downloader(QObject):
    if pyqtSignal:
        progress = pyqtSignal()

    def __init__(self, torrent_info: TorrentInfo, our_peer_id: bytes,
                 logger: logging.Logger, file_structure: FileStructure,
                 peer_manager: PeerManager, announcer: Announcer):
        super().__init__()

        self._torrent_info = torrent_info
        self._download_info = torrent_info.download_info
        self._our_peer_id = our_peer_id

        self._logger = glklog
        self._file_structure = file_structure
        self._peer_manager = peer_manager
        self._announcer = announcer

        self._request_executors = []  # type: List[asyncio.Task]

        self._executors_processed_requests = []  # type: List[List[BlockRequestFuture]]

        self._non_started_pieces = None   # type: List[int]
        self._download_start_time = None  # type: float

        self._piece_block_queue = OrderedDict()

        self._endgame_mode = False
        self._tasks_waiting_for_more_peers = 0
        self._request_deque_relevant = asyncio.Event()

        self._last_piece_finish_signal_time = None  # type: Optional[float]

    REQUEST_LENGTH = 2 ** 14

    def _get_piece_position(self, index: int) -> Tuple[int, int]:
        piece_offset = index * self._download_info.piece_length
        cur_piece_length = self._download_info.get_real_piece_length(index)
        return piece_offset, cur_piece_length

    async def _flush_piece(self, index: int):
        piece_offset, cur_piece_length = self._get_piece_position(index)
        await self._file_structure.flush(piece_offset, cur_piece_length)

    FLAG_TRANSMISSION_TIMEOUT = 0.5

    def _send_cancels(self, request: BlockRequestFuture):
        performers = request.prev_performers
        if request.performer is not None:
            performers.add(request.performer)
        source = request.result()
        peer_data = self._peer_manager.peer_data
        for peer in performers - {source}:
            if peer in peer_data:
                peer_data[peer].client.send_request(request, cancel=True)

    def _start_downloading_piece(self, piece_index: int):
        piece_info = self._download_info.pieces[piece_index]

        blocks_expected = piece_info.blocks_expected
        request_deque = deque()
        for block_begin in range(0, piece_info.length, Downloader.REQUEST_LENGTH):
            block_end = min(block_begin + Downloader.REQUEST_LENGTH, piece_info.length)
            block_length = block_end - block_begin
            request = BlockRequestFuture(piece_index, block_begin, block_length)
            request.add_done_callback(self._send_cancels)

            blocks_expected.add(request)
            request_deque.append(request)
        self._piece_block_queue[piece_index] = request_deque

        self._download_info.interesting_pieces.add(piece_index)
        peer_data = self._peer_manager.peer_data
        for peer in piece_info.owners:
            peer_data[peer].client.am_interested = True

        concurrent_peers_count = sum(1 for peer, data in peer_data.items() if data.queue_size)
        # self._logger.debug('piece %s started (owned by %s alive peers, concurrency: %s peers)',
        #                    piece_index, len(piece_info.owners), concurrent_peers_count)
        #self._logger.debug(
        #    f'piece {piece_index} started '
        #    f'(owned by {len(piece_info.owners)} alive peers, '
        #    f'concurrency: {concurrent_peers_count} peers)')

    PIECE_FINISH_SIGNAL_MIN_INTERVAL = 1

    def _finish_downloading_piece(self, piece_index: int):
        piece_info = self._download_info.pieces[piece_index]

        piece_info.mark_as_downloaded()
        self._download_info.downloaded_piece_count += 1

        self._download_info.interesting_pieces.remove(piece_index)
        peer_data = self._peer_manager.peer_data
        for peer in piece_info.owners:
            client = peer_data[peer].client
            for index in self._download_info.interesting_pieces:
                if client.piece_owned[index]:
                    break
            else:
                client.am_interested = False

        for data in peer_data.values():
            data.client.send_have(piece_index)

        #self._logger.debug(f'piece {piece_index} finished')

        torrent_state = TorrentState(self._torrent_info)

        # self._logger.info('progress %.1lf%% (%s / %s pieces)', floor_to(torrent_state.progress * 100, 1),
        #                   self._download_info.downloaded_piece_count, torrent_state.selected_piece_count)

        #self._logger.info(
        #    'progress {progress} % ({count} / {total} pieces)'.format(
        #        progress=floor_to(torrent_state.progress * 100, 1),
        #        count=self._download_info.downloaded_piece_count,
        #        total=torrent_state.selected_piece_count)
        #)

        if pyqtSignal and self._download_info.downloaded_piece_count < torrent_state.selected_piece_count:
            cur_time = time.time()
            if self._last_piece_finish_signal_time is None or \
                    cur_time - self._last_piece_finish_signal_time >= Downloader.PIECE_FINISH_SIGNAL_MIN_INTERVAL:
                self.progress.emit()
                self._last_piece_finish_signal_time = time.time()
            # If the signal isn't emitted, the GUI will be updated after the next speed measurement anyway

    async def _validate_piece(self, piece_index: int):
        piece_info = self._download_info.pieces[piece_index]

        assert piece_info.are_all_blocks_downloaded()

        piece_offset, cur_piece_length = self._get_piece_position(piece_index)
        data = await self._file_structure.read(piece_offset, cur_piece_length)
        actual_digest = hashlib.sha1(data).digest()
        if actual_digest == piece_info.piece_hash:
            await self._flush_piece(piece_index)
            self._finish_downloading_piece(piece_index)
            return

        peer_data = self._peer_manager.peer_data
        for peer in piece_info.sources:
            self._download_info.increase_distrust(peer)
            if self._download_info.is_banned(peer):
                #self._logger.info(f'Host {peer.host} banned')
                peer_data[peer].client_task.cancel()

        piece_info.reset_content()
        self._start_downloading_piece(piece_index)

        #self._logger.debug(f'piece {piece_index} not valid, redownloading')

    _INF = float('inf')

    HANG_PENALTY_DURATION = 10
    HANG_PENALTY_COEFF = 100

    def get_peer_download_rate(self, peer: Peer) -> int:
        data = self._peer_manager.peer_data[peer]

        rate = data.client.downloaded  # To reach maximal download speed
        if data.hanged_time is not None and time.time() - data.hanged_time <= Downloader.HANG_PENALTY_DURATION:
            rate //= Downloader.HANG_PENALTY_COEFF
        return rate

    DOWNLOAD_PEER_COUNT = 15

    def _request_piece_blocks(self, max_pending_count: int, piece_index: int) -> Iterator[BlockRequestFuture]:
        if not max_pending_count:
            return
        piece_info = self._download_info.pieces[piece_index]
        peer_data = self._peer_manager.peer_data

        request_deque = self._piece_block_queue[piece_index]
        performer = None
        performer_data = None
        pending_count = 0
        while request_deque:
            request = request_deque[0]
            if request.done():
                request_deque.popleft()

                yield request
                continue

            if performer is None or not performer_data.is_free():
                available_peers = {peer for peer in piece_info.owners
                                   if peer_data[peer].is_available()}
                if not available_peers:
                    return
                performer = max(available_peers, key=self.get_peer_download_rate)
                performer_data = peer_data[performer]
            request_deque.popleft()
            performer_data.queue_size += 1

            request.performer = performer
            performer_data.client.send_request(request)
            yield request

            pending_count += 1
            if pending_count == max_pending_count:
                return

    RAREST_PIECE_COUNT_TO_SELECT = 10

    def _select_new_piece(self, *, force: bool) -> Optional[int]:
        is_appropriate = PeerData.is_free if force else PeerData.is_available
        appropriate_peers = {peer for peer, data in self._peer_manager.peer_data.items() if is_appropriate(data)}
        if not appropriate_peers:
            return None

        pieces = self._download_info.pieces
        available_pieces = [index for index in self._non_started_pieces
                            if appropriate_peers & pieces[index].owners]
        if not available_pieces:
            return None

        available_pieces.sort(key=lambda index: len(pieces[index].owners))
        piece_count_to_select = min(len(available_pieces), Downloader.RAREST_PIECE_COUNT_TO_SELECT)
        return available_pieces[random.randint(0, piece_count_to_select - 1)]

    _typical_piece_length = 2 ** 20
    _requests_per_piece = ceil(_typical_piece_length / REQUEST_LENGTH)
    _desired_request_stock = DOWNLOAD_PEER_COUNT * PeerData.DOWNLOAD_REQUEST_QUEUE_SIZE
    DESIRED_PIECE_STOCK = ceil(_desired_request_stock / _requests_per_piece)

    def _request_blocks(self, max_pending_count: int) -> List[BlockRequestFuture]:
        result = []
        pending_count = 0
        consumed_pieces = []
        try:
            for piece_index, request_deque in self._piece_block_queue.items():
                piece_requests = list(self._request_piece_blocks(max_pending_count - pending_count, piece_index))
                result += piece_requests
                pending_count += sum(1 for request in piece_requests if not request.done())
                if not request_deque:
                    consumed_pieces.append(piece_index)
                if pending_count == max_pending_count:
                    return result

            piece_stock = len(self._piece_block_queue) - len(consumed_pieces)
            piece_stock_small = (piece_stock < Downloader.DESIRED_PIECE_STOCK)
            new_piece_index = self._select_new_piece(force=piece_stock_small)
            if new_piece_index is not None:
                self._non_started_pieces.remove(new_piece_index)
                self._start_downloading_piece(new_piece_index)

                result += list(self._request_piece_blocks(max_pending_count - pending_count, new_piece_index))
                if not self._piece_block_queue[new_piece_index]:
                    consumed_pieces.append(new_piece_index)
        finally:
            for piece_index in consumed_pieces:
                del self._piece_block_queue[piece_index]

        if not result:
            if not self._piece_block_queue and not self._non_started_pieces:
                raise NoRequestsError('No more undistributed requests')
            raise NotEnoughPeersError('No peers to perform a request')
        return result

    DOWNLOAD_PEERS_ACTIVE_TO_REQUEST_MORE_PEERS = 2

    NO_PEERS_SLEEP_TIME = 3
    STARTING_DURATION = 5
    NO_PEERS_SLEEP_TIME_ON_STARTING = 1

    RECONNECT_TIMEOUT = 50

    async def _wait_more_peers(self):
        self._tasks_waiting_for_more_peers += 1
        download_peers_active = Downloader.DOWNLOAD_PEER_COUNT - self._tasks_waiting_for_more_peers
        if download_peers_active <= Downloader.DOWNLOAD_PEERS_ACTIVE_TO_REQUEST_MORE_PEERS and \
                len(self._peer_manager.peer_data) < PeerManager.MAX_PEERS_TO_ACTIVELY_CONNECT:
            cur_time = time.time()
            if self._peer_manager.last_connecting_time is None or \
                    cur_time - self._peer_manager.last_connecting_time >= Downloader.RECONNECT_TIMEOUT:
                # This can recover connections to peers after temporary loss of Internet connection
                # self._logger.info('trying to reconnect to peers')
                self._peer_manager.connect_to_peers(self._announcer.last_tracker_client.peers, True)

            self._announcer.more_peers_requested.set()

        if time.time() - self._download_start_time <= Downloader.STARTING_DURATION:
            sleep_time = Downloader.NO_PEERS_SLEEP_TIME_ON_STARTING
        else:
            sleep_time = Downloader.NO_PEERS_SLEEP_TIME
        await asyncio.sleep(sleep_time)
        self._tasks_waiting_for_more_peers -= 1

    def _get_non_finished_pieces(self) -> List[int]:
        pieces = self._download_info.pieces
        return [i for i in range(self._download_info.piece_count)
                if pieces[i].selected and not pieces[i].downloaded]

    async def _wait_more_requests(self):
        if not self._endgame_mode:
            #self._logger.info(
            #    'entering endgame mode (remaining pieces: {pieces})'.format(
            #          pieces=', '.join(map(str, self._get_non_finished_pieces()))))
            self._endgame_mode = True

        await self._request_deque_relevant.wait()

    REQUEST_TIMEOUT = 6
    REQUEST_TIMEOUT_ENDGAME = 1

    async def _execute_block_requests(self, processed_requests: List[BlockRequestFuture]):
        while True:
            try:
                max_pending_count = PeerData.DOWNLOAD_REQUEST_QUEUE_SIZE - len(processed_requests)
                if max_pending_count > 0:
                    processed_requests += self._request_blocks(max_pending_count)
            except NotEnoughPeersError:
                if not processed_requests:
                    await self._wait_more_peers()
                    continue
            except NoRequestsError:
                if not processed_requests:
                    if not any(self._executors_processed_requests):
                        self._request_deque_relevant.set()
                        return
                    await self._wait_more_requests()
                    continue

            if self._endgame_mode:
                request_timeout = Downloader.REQUEST_TIMEOUT_ENDGAME
            else:
                request_timeout = Downloader.REQUEST_TIMEOUT
            requests_done, requests_pending = await asyncio.wait(
                processed_requests, return_when=asyncio.FIRST_COMPLETED, timeout=request_timeout)

            peer_data = self._peer_manager.peer_data
            if len(requests_pending) < len(processed_requests):
                pieces = self._download_info.pieces
                for request in requests_done:
                    if request.performer in peer_data:
                        peer_data[request.performer].queue_size -= 1

                    piece_info = pieces[request.piece_index]
                    if not piece_info.validating and not piece_info.downloaded and not piece_info.blocks_expected:
                        piece_info.validating = True
                        await self._validate_piece(request.piece_index)
                        piece_info.validating = False
                processed_requests.clear()
                processed_requests += list(requests_pending)
            else:
                hanged_peers = {request.performer for request in requests_pending} & set(peer_data.keys())
                cur_time = time.time()
                for peer in hanged_peers:
                    peer_data[peer].hanged_time = cur_time
                if hanged_peers:
                    #self._logger.debug(
                    #    'peers {peers} hanged'.format(
                    #        peers=', '.join(map(str, hanged_peers))))
                    pass

                for request in requests_pending:
                    if request.performer in peer_data:
                        peer_data[request.performer].queue_size -= 1
                        request.prev_performers.add(request.performer)
                    request.performer = None

                    self._piece_block_queue.setdefault(request.piece_index, deque()).append(request)
                processed_requests.clear()
                self._request_deque_relevant.set()
                self._request_deque_relevant.clear()

    async def run(self):
        self._non_started_pieces = self._get_non_finished_pieces()
        self._download_start_time = time.time()

        # self._logger.info(
        #     f'Starting download in '
        #    f'{self._download_info.download_dir}')

        if not self._non_started_pieces:
            self._download_info.complete = True
            return

        random.shuffle(self._non_started_pieces)

        for _ in range(Downloader.DOWNLOAD_PEER_COUNT):
            processed_requests = []
            self._executors_processed_requests.append(processed_requests)
            self._request_executors.append(asyncio.ensure_future(self._execute_block_requests(processed_requests)))

        await asyncio.wait(self._request_executors)

        self._logger.info('Torrent file download complete')

        self._download_info.complete = True
        await self._announcer.try_to_announce(EventType.completed)

        if self._torrent_info.ipfsImportWhenComplete:
            self._logger.info('Move to IPFS')
            await self.ipfsImport(self._torrent_info)

        if pyqtSignal:
            self.progress.emit()

        # for peer, data in self._peer_manager.peer_data.items():
        #     if data.client.is_seed():
        #         data.client_task.cancel()

    @ipfsOp
    async def ipfsImport(self, ipfsop, torrent_info):
        try:
            entry = await ipfsop.addPath(torrent_info.download_dir)
            glklog.debug(f'Torrent import: {entry}')
        except Exception as err:
            glklog.debug(f'Torrent import error: {err}')

    async def stop(self):
        for task in self._request_executors:
            task.cancel()
        if self._request_executors:
            await asyncio.wait(self._request_executors)
