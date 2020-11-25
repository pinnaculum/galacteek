import asyncio
import copy
import hashlib
import random
import socket
import struct
import time
from collections import OrderedDict
from math import ceil
from typing import List, Set, cast, Optional, Dict, Union, Any, Iterator

import bencodepy
from bitarray import bitarray

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QObject


from galacteek.torrent.utils import grouper


def generate_peer_id():
    return bytes(random.randint(0, 255) for _ in range(20))


class Peer:
    def __init__(self, host: str, port: int, peer_id: bytes=None):
        # FIXME: Need we typecheck for the case of malicious data?

        self._host = host
        self._port = port
        self.peer_id = peer_id

        self._hash = hash((host, port))  # Important for performance

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    def __eq__(self, other):
        if not isinstance(other, Peer):
            return False
        return self._host == other._host and self._port == other._port

    def __hash__(self):
        return self._hash

    @classmethod
    def from_dict(cls, dictionary: OrderedDict):
        return cls(dictionary[b'ip'].decode(), dictionary[b'port'], dictionary.get(b'peer id'))

    @classmethod
    def from_compact_form(cls, data: bytes):
        ip, port = struct.unpack('!4sH', data)
        host = socket.inet_ntoa(ip)
        return cls(host, port)

    def __repr__(self):
        return '{}:{}'.format(self._host, self._port)


def get_utf8(dictionary: OrderedDict, key: bytes):
    assert isinstance(key, bytes)

    suffixed_key = key + b'.utf-8'
    if suffixed_key in dictionary:
        return dictionary[suffixed_key]
    return dictionary[key]


class FileInfo:
    def __init__(self, length: int, path: List[str], *, md5sum: str=None):
        self._length = length
        self._path = path
        self._md5sum = md5sum

        self.offset = None
        self.selected = True

    @property
    def length(self) -> int:
        return self._length

    @property
    def path(self) -> List[str]:
        return self._path

    @property
    def md5sum(self) -> str:
        return self._md5sum

    @classmethod
    def from_dict(cls, dictionary: OrderedDict):
        try:
            path = list(map(bytes.decode, get_utf8(dictionary, b'path')))
        except KeyError:
            path = []

        return cls(dictionary[b'length'], path, md5sum=dictionary.get(b'md5sum'))


class BlockRequest:
    def __init__(self, piece_index: int, block_begin: int, block_length: int):
        self.piece_index = piece_index
        self.block_begin = block_begin
        self.block_length = block_length

    def __eq__(self, other):
        if not isinstance(other, BlockRequest):
            return False
        return self.__dict__ == other.__dict__

    def __hash__(self):
        return hash((self.piece_index, self.block_begin, self.block_length))


class BlockRequestFuture(asyncio.Future, BlockRequest):
    def __init__(self, piece_index: int, block_begin: int, block_length: int):
        asyncio.Future.__init__(self)
        BlockRequest.__init__(self, piece_index, block_begin, block_length)

        self.prev_performers = set()
        self.performer = None

    __eq__ = asyncio.Future.__eq__
    __hash__ = asyncio.Future.__hash__


SHA1_DIGEST_LEN = 20


class PieceInfo:
    def __init__(self, piece_hash: bytes, length: int):
        self._piece_hash = piece_hash
        self._length = length

        self.selected = True
        self.owners = set()  # type: Set[Peer]

        self.validating = False

        self._downloaded = None
        self._sources = None
        self._block_downloaded = None  # type: Optional[bitarray]
        self._blocks_expected = None
        self.reset_content()

    def reset_content(self):
        self._downloaded = False
        self._sources = set()

        self._block_downloaded = None
        self._blocks_expected = set()

    def reset_run_state(self):
        self.owners = set()

        self.validating = False

        self._blocks_expected = set()

    @property
    def piece_hash(self) -> bytes:
        return self._piece_hash

    @property
    def length(self) -> int:
        return self._length

    @property
    def downloaded(self) -> bool:
        return self._downloaded

    @property
    def sources(self) -> Set[Peer]:
        return self._sources

    @property
    def blocks_expected(self) -> Optional[Set[BlockRequestFuture]]:
        return self._blocks_expected

    def mark_downloaded_blocks(self, source: Peer, request: BlockRequest):
        if self._downloaded:
            raise ValueError('The whole piece is already downloaded')

        self._sources.add(source)

        arr = self._block_downloaded
        if arr is None:
            arr = bitarray(ceil(self._length / DownloadInfo.MARKED_BLOCK_SIZE))
            arr.setall(False)
            self._block_downloaded = arr

        mark_begin = ceil(request.block_begin / DownloadInfo.MARKED_BLOCK_SIZE)
        if request.block_begin + request.block_length == self._length:
            mark_end = len(arr)
        else:
            mark_end = (request.block_begin + request.block_length) // DownloadInfo.MARKED_BLOCK_SIZE
        arr[mark_begin:mark_end] = True

        blocks_expected = cast(Set[BlockRequestFuture], self._blocks_expected)
        downloaded_blocks = []
        for fut in blocks_expected:
            query_begin = fut.block_begin // DownloadInfo.MARKED_BLOCK_SIZE
            query_end = ceil((fut.block_begin + fut.block_length) / DownloadInfo.MARKED_BLOCK_SIZE)
            if arr[query_begin:query_end].all():
                downloaded_blocks.append(fut)
                fut.set_result(source)
        for fut in downloaded_blocks:
            blocks_expected.remove(fut)

    def are_all_blocks_downloaded(self) -> bool:
        return self._downloaded or (self._block_downloaded is not None and self._block_downloaded.all())

    def mark_as_downloaded(self):
        if self._downloaded:
            raise ValueError('The piece is already downloaded')

        self._downloaded = True

        # Delete data structures for this piece to save memory
        self._sources = None
        self._block_downloaded = None
        self._blocks_expected = None


class SessionStatistics:
    def __init__(self, prev_session_stats: Optional['SessionStatistics']):
        self.peer_count = 0
        self._peer_last_download = {}
        self._peer_last_upload = {}
        self._downloaded_per_session = 0
        self._uploaded_per_session = 0
        self.download_speed = None  # type: Optional[float]
        self.upload_speed = None    # type: Optional[float]

        if prev_session_stats is not None:
            self._total_downloaded = prev_session_stats.total_downloaded
            self._total_uploaded = prev_session_stats.total_uploaded
        else:
            self._total_downloaded = 0
            self._total_uploaded = 0

    @property
    def peer_last_download(self) -> Dict[Peer, float]:
        return self._peer_last_download

    @property
    def peer_last_upload(self) -> Dict[Peer, float]:
        return self._peer_last_upload

    @property
    def downloaded_per_session(self) -> int:
        return self._downloaded_per_session

    @property
    def uploaded_per_session(self) -> int:
        return self._uploaded_per_session

    PEER_CONSIDERATION_TIME = 10

    @staticmethod
    def _get_actual_peer_count(time_dict: Dict[Peer, float]) -> int:
        cur_time = time.time()
        return sum(1 for t in time_dict.values() if cur_time - t <= SessionStatistics.PEER_CONSIDERATION_TIME)

    @property
    def downloading_peer_count(self) -> int:
        return SessionStatistics._get_actual_peer_count(self._peer_last_download)

    @property
    def uploading_peer_count(self) -> int:
        return SessionStatistics._get_actual_peer_count(self._peer_last_upload)

    @property
    def total_downloaded(self) -> int:
        return self._total_downloaded

    @property
    def total_uploaded(self) -> int:
        return self._total_uploaded

    def add_downloaded(self, peer: Peer, size: int):
        self._peer_last_download[peer] = time.time()
        self._downloaded_per_session += size
        self._total_downloaded += size

    def add_uploaded(self, peer: Peer, size: int):
        self._peer_last_upload[peer] = time.time()
        self._uploaded_per_session += size
        self._total_uploaded += size


FileTreeNode = Union[FileInfo, Dict[str, Any]]


class DownloadInfo:
    MARKED_BLOCK_SIZE = 2 ** 10

    completed = pyqtSignal(bool)

    def __init__(self, info_hash: bytes,
                 piece_length: int, piece_hashes: List[bytes], suggested_name: str, files: List[FileInfo], *,
                 private: bool=False):
        self.info_hash = info_hash
        self.piece_length = piece_length
        self.suggested_name = suggested_name

        self.files = files
        self._file_tree = {}
        self._create_file_tree()

        self.private = private

        assert piece_hashes
        self._pieces = [PieceInfo(item, piece_length) for item in piece_hashes[:-1]]
        last_piece_length = self.total_size - (len(piece_hashes) - 1) * self.piece_length
        self._pieces.append(PieceInfo(piece_hashes[-1], last_piece_length))

        piece_count = len(piece_hashes)
        if ceil(self.total_size / piece_length) != piece_count:
            raise ValueError('Invalid count of piece hashes')

        self._interesting_pieces = None
        self.downloaded_piece_count = 0
        self._complete = False

        self._host_distrust_rates = {}

        self._session_statistics = SessionStatistics(None)

    @property
    def single_file_mode(self) -> bool:
        return len(self.files) == 1 and not self.files[0].path

    def _create_file_tree(self):
        offset = 0
        for item in self.files:
            item.offset = offset
            offset += item.length

            if not item.path:
                self._file_tree = item
            else:
                directory = self._file_tree
                for elem in item.path[:-1]:
                    directory = directory.setdefault(elem, {})
                directory[item.path[-1]] = item

    @property
    def file_tree(self) -> FileTreeNode:
        return self._file_tree

    def _get_file_tree_node(self, path: List[str]) -> FileTreeNode:
        result = self._file_tree
        try:
            for elem in path:
                result = result[elem]
        except KeyError:
            raise ValueError("Path \"{}\" doesn't exist in this torrent".format('/'.join(path)))
        return result

    @staticmethod
    def _traverse_nodes(node: FileTreeNode) -> Iterator[FileInfo]:
        if isinstance(node, FileInfo):
            yield node
            return
        for child in node.values():
            yield from DownloadInfo._traverse_nodes(child)

    def select_files(self, paths: List[List[str]], mode: str):
        if mode not in ('whitelist', 'blacklist'):
            raise ValueError('Invalid mode "{}"'.format(mode))
        include_paths = (mode == 'whitelist')

        for info in self.pieces:
            info.selected = not include_paths
        for info in self.files:
            info.selected = not include_paths

        segments = []
        for path in paths:
            for node in DownloadInfo._traverse_nodes(self._get_file_tree_node(path)):
                node.selected = include_paths
                segments.append((node.offset, node.length))
        if (include_paths and not segments) or (not include_paths and len(segments) == len(self.files)):
            raise ValueError("Can't exclude all files from the torrent")

        segments.sort()
        united_segments = []
        for cur_segment in segments:
            if united_segments:
                last_segment = united_segments[-1]
                if last_segment[0] + last_segment[1] == cur_segment[0]:
                    united_segments[-1] = (last_segment[0], last_segment[1] + cur_segment[1])
                    continue
            united_segments.append(cur_segment)

        for offset, length in united_segments:
            if include_paths:
                piece_begin = offset // self.piece_length
                piece_end = ceil((offset + length) / self.piece_length)
            else:
                piece_begin = ceil(offset / self.piece_length)
                piece_end = (offset + length) // self.piece_length

            for index in range(piece_begin, piece_end):
                self.pieces[index].selected = include_paths

    def reset_run_state(self):
        self._pieces = [copy.copy(info) for info in self._pieces]
        for info in self._pieces:
            info.reset_run_state()

        self._interesting_pieces = set()

    def reset_stats(self):
        self._session_statistics = SessionStatistics(self._session_statistics)

    @classmethod
    def from_dict(cls, dictionary: OrderedDict):
        info_hash = hashlib.sha1(bencodepy.encode(dictionary)).digest()

        if len(dictionary[b'pieces']) % SHA1_DIGEST_LEN != 0:
            raise ValueError('Invalid length of "pieces" string')
        piece_hashes = grouper(dictionary[b'pieces'], SHA1_DIGEST_LEN)

        if b'files' in dictionary:
            files = list(map(FileInfo.from_dict, dictionary[b'files']))
        else:
            files = [FileInfo.from_dict(dictionary)]

        return cls(info_hash,
                   dictionary[b'piece length'], piece_hashes, get_utf8(dictionary, b'name').decode(), files,
                   private=dictionary.get('private', False))

    @property
    def pieces(self) -> List[PieceInfo]:
        return self._pieces

    @property
    def piece_count(self) -> int:
        return len(self._pieces)

    def get_real_piece_length(self, index: int) -> int:
        if index == self.piece_count - 1:
            return self.total_size - self.piece_length * (self.piece_count - 1)
        else:
            return self.piece_length

    @property
    def total_size(self) -> int:
        return sum(file.length for file in self.files)

    @property
    def bytes_left(self) -> int:
        result = (self.piece_count - self.downloaded_piece_count) * self.piece_length
        last_piece_index = self.piece_count - 1
        if not self._pieces[last_piece_index].downloaded:
            result += self._pieces[last_piece_index].length - self.piece_length
        return result

    @property
    def interesting_pieces(self) -> Set[int]:
        return self._interesting_pieces

    @property
    def complete(self) -> bool:
        return self._complete

    @complete.setter
    def complete(self, value: bool):
        if value:
            assert all(info.downloaded or not info.selected for info in self._pieces)
        self._complete = value

        self.completed.emit(value)

    DISTRUST_RATE_TO_BAN = 5

    def increase_distrust(self, peer: Peer):
        self._host_distrust_rates[peer.host] = self._host_distrust_rates.get(peer.host, 0) + 1

    def is_banned(self, peer: Peer) -> bool:
        return (peer.host in self._host_distrust_rates and
                self._host_distrust_rates[peer.host] >= DownloadInfo.DISTRUST_RATE_TO_BAN)

    @property
    def session_statistics(self) -> SessionStatistics:
        return self._session_statistics


class TorrentInfo:
    def __init__(self, download_info: DownloadInfo, announce_list: List[List[str]], *, download_dir: str):
        # TODO: maybe implement optional fields

        self.download_info = download_info
        self._announce_list = announce_list

        self.download_dir = download_dir

        self.ipfsImportWhenComplete = False

        self.paused = False

    @classmethod
    def from_file(cls, filename: str, **kwargs):
        dictionary = cast(OrderedDict, bencodepy.decode_from_file(filename))
        download_info = DownloadInfo.from_dict(dictionary[b'info'])

        if b'announce-list' in dictionary:
            announce_list = [[url.decode() for url in tier]
                             for tier in dictionary[b'announce-list']]
        else:
            announce_list = [[dictionary[b'announce'].decode()]]

        return cls(download_info, announce_list, **kwargs)

    @classmethod
    def from_data(cls, data: bytes, **kwargs):
        # TODO: refactor from_{data,filename}

        dictionary = cast(OrderedDict, bencodepy.decode(data))
        download_info = DownloadInfo.from_dict(dictionary[b'info'])

        if b'announce-list' in dictionary:
            announce_list = [[url.decode() for url in tier]
                             for tier in dictionary[b'announce-list']]
        else:
            announce_list = [[dictionary[b'announce'].decode()]]

        return cls(download_info, announce_list, **kwargs)

    @property
    def announce_list(self) -> List[List[str]]:
        return self._announce_list


class TorrentState:
    """This class represents crucial parameters of torrent state. Unlike TorrentInfo and DownloadInfo,
    it is too small to serialize (to send it via socket as an answer to `status` command) and
    thread-safe (we can pass it to a GUI thread).
    """

    def __init__(self, torrent_info: TorrentInfo):
        download_info = torrent_info.download_info
        statistics = download_info.session_statistics

        self.suggested_name = download_info.suggested_name
        self.info_hash = download_info.info_hash
        self.single_file_mode = download_info.single_file_mode

        self.total_piece_count = len(download_info.pieces)
        self.selected_piece_count = sum(1 for info in download_info.pieces if info.selected)

        last_piece_info = download_info.pieces[-1]
        self.selected_size = self.selected_piece_count * download_info.piece_length
        if last_piece_info.selected:
            self.selected_size += last_piece_info.length - download_info.piece_length
        self.downloaded_size = download_info.downloaded_piece_count * download_info.piece_length
        if last_piece_info.downloaded:
            self.downloaded_size += last_piece_info.length - download_info.piece_length

        self.total_file_count = len(download_info.files)
        self.selected_file_count = sum(1 for info in download_info.files if info.selected)

        self.download_dir = torrent_info.download_dir

        self.paused = torrent_info.paused
        self.complete = download_info.complete

        self.total_peer_count = statistics.peer_count
        self.downloading_peer_count = statistics.downloading_peer_count
        self.uploading_peer_count = statistics.uploading_peer_count

        self.download_speed = statistics.download_speed
        self.upload_speed = statistics.upload_speed

        self.total_uploaded = statistics.total_uploaded
        self.total_downloaded = statistics.total_downloaded

    MIN_SPEED_TO_CALC_ETA = 100 * 2 ** 10  # = 100 KiB/s

    @property
    def eta_seconds(self) -> Optional[int]:
        if self.download_speed is not None and self.download_speed >= TorrentState.MIN_SPEED_TO_CALC_ETA:
            return (self.selected_size - self.downloaded_size) / self.download_speed
        else:
            return None

    @property
    def ratio(self) -> float:
        return self.total_uploaded / self.total_downloaded if self.total_downloaded else 0

    @property
    def progress(self) -> float:
        return self.downloaded_size / self.selected_size
