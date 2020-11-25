import asyncio
import logging
import struct
from enum import Enum
from math import ceil
from typing import Optional, Tuple, List, cast, Sequence

from bitarray import bitarray

from galacteek import log
from galacteek.torrent.file_structure import FileStructure
from galacteek.torrent.models import SHA1_DIGEST_LEN, DownloadInfo, Peer, BlockRequest


__all__ = ['PeerTCPClient']


class MessageType(Enum):
    choke = 0
    unchoke = 1
    interested = 2
    not_interested = 3
    have = 4
    bitfield = 5
    request = 6
    piece = 7
    cancel = 8
    port = 9


class SeedError(Exception):
    pass


class PeerTCPClient:
    LOGGER_LEVEL = logging.INFO

    def __init__(self, our_peer_id: bytes, peer: Peer):
        self._our_peer_id = our_peer_id
        self._peer = peer

        # self._logger = logging.getLogger('[{}]'.format(peer))
        # self._logger.setLevel(PeerTCPClient.LOGGER_LEVEL)
        self._logger = log

        self._download_info = None   # type: DownloadInfo
        self._file_structure = None  # type: FileStructure
        self._piece_owned = None     # type: bitarray

        self._am_choking = True
        self._am_interested = False
        self._peer_choking = True
        self._peer_interested = False

        self._downloaded = 0
        self._uploaded = 0

        self._reader = None               # type: asyncio.StreamReader
        self._writer = None               # type: asyncio.StreamWriter
        self._connected = False

    _handshake_message = b'BitTorrent protocol'
    HANDSHAKE_DATA = bytes([len(_handshake_message)]) + _handshake_message
    RESERVED_BYTES = b'\0' * 8

    CONNECT_TIMEOUT = 5
    READ_TIMEOUT = 5
    MAX_SILENCE_DURATION = 3 * 60
    WRITE_TIMEOUT = 5

    def _send_protocol_data(self):
        self._writer.write(PeerTCPClient.HANDSHAKE_DATA + PeerTCPClient.RESERVED_BYTES)

    async def _receive_protocol_data(self):
        data_len = len(PeerTCPClient.HANDSHAKE_DATA) + len(PeerTCPClient.RESERVED_BYTES)
        response = await asyncio.wait_for(self._reader.readexactly(data_len), PeerTCPClient.READ_TIMEOUT)

        if response[:len(PeerTCPClient.HANDSHAKE_DATA)] != PeerTCPClient.HANDSHAKE_DATA:
            raise ValueError('Unknown protocol')

    def _populate_info(self, download_info: DownloadInfo, file_structure: FileStructure):
        self._download_info = download_info
        self._file_structure = file_structure
        self._piece_owned = bitarray(download_info.piece_count)
        self._piece_owned.setall(False)

        self._writer.write(self._download_info.info_hash + self._our_peer_id)

    async def _receive_info(self) -> bytes:
        data_len = SHA1_DIGEST_LEN + len(self._our_peer_id)
        response = await asyncio.wait_for(self._reader.readexactly(data_len), PeerTCPClient.READ_TIMEOUT)

        actual_info_hash = response[:SHA1_DIGEST_LEN]
        actual_peer_id = response[SHA1_DIGEST_LEN:]
        if self._our_peer_id == actual_peer_id:
            raise ValueError('Connection to ourselves')
        if self._peer.peer_id is not None and self._peer.peer_id != actual_peer_id:
            raise ValueError('Unexpected peer_id')
        self._peer.peer_id = actual_peer_id

        return actual_info_hash

    async def connect(self, download_info: DownloadInfo, file_structure: FileStructure):
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(self._peer.host, self._peer.port), PeerTCPClient.CONNECT_TIMEOUT)

        self._send_protocol_data()
        self._populate_info(download_info, file_structure)

        await self._receive_protocol_data()
        if await self._receive_info() != download_info.info_hash:
            raise ValueError("info_hashes don't match")

        self._send_bitfield()
        self._connected = True

    async def accept(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> bytes:
        self._reader = reader
        self._writer = writer

        self._send_protocol_data()

        await self._receive_protocol_data()
        return await self._receive_info()

    def confirm_info_hash(self, download_info: DownloadInfo, file_structure: FileStructure):
        self._populate_info(download_info, file_structure)

        self._send_bitfield()
        self._connected = True

    MAX_MESSAGE_LENGTH = 2 ** 18

    async def _receive_message(self) -> Optional[Tuple[MessageType, memoryview]]:
        data = await asyncio.wait_for(self._reader.readexactly(4), PeerTCPClient.MAX_SILENCE_DURATION)
        (length,) = struct.unpack('!I', data)
        if length == 0:  # keep-alive
            return None
        if length > PeerTCPClient.MAX_MESSAGE_LENGTH:
            raise ValueError('Message length is too big')

        data = await asyncio.wait_for(self._reader.readexactly(length), PeerTCPClient.READ_TIMEOUT)
        try:
            message_id = MessageType(data[0])
        except ValueError:
            self._logger.debug('Unknown message type %s', data[0])
            return None
        payload = memoryview(data)[1:]

        # self._logger.debug('incoming message %s length=%s', message_id.name, length)

        await asyncio.sleep(0.05)

        return message_id, payload

    _KEEP_ALIVE_MESSAGE = b'\0' * 4

    def _send_message(self, message_id: MessageType=None, *payload: List[bytes]):
        if message_id is None:  # keep-alive
            self._writer.write(PeerTCPClient._KEEP_ALIVE_MESSAGE)
            return

        length = sum(len(portion) for portion in payload) + 1
        # self._logger.debug('outcoming message %s length=%s', message_id.name, length)

        self._writer.write(struct.pack('!IB', length, message_id.value))
        for portion in payload:
            self._writer.write(portion)

    @property
    def am_choking(self):
        return self._am_choking

    @property
    def am_interested(self):
        return self._am_interested

    def _check_connect(self):
        if not self._connected:
            raise RuntimeError("Can't change state when the client isn't connected")

    @am_choking.setter
    def am_choking(self, value: bool):
        self._check_connect()
        if self._am_choking != value:
            self._am_choking = value
            self._send_message(MessageType.choke if value else MessageType.unchoke)

    @am_interested.setter
    def am_interested(self, value: bool):
        self._check_connect()
        if self._am_interested != value:
            self._am_interested = value
            self._send_message(MessageType.interested if value else MessageType.not_interested)

    @property
    def peer_choking(self):
        return self._peer_choking

    @property
    def peer_interested(self):
        return self._peer_interested

    @property
    def piece_owned(self) -> Sequence[bool]:
        return self._piece_owned

    # def is_seed(self) -> bool:
    #     return self._piece_owned & self._download_info.piece_selected == self._download_info.piece_selected

    @property
    def downloaded(self):
        return self._downloaded

    @property
    def uploaded(self):
        return self._uploaded

    @staticmethod
    def _check_payload_len(message_id: MessageType, payload: memoryview, expected_len: int):
        if len(payload) != expected_len:
            raise ValueError('Invalid payload length on message_id = {} '
                             '(expected {}, got {})'.format(message_id.name, expected_len, len(payload)))

    def _handle_setting_states(self, message_id: MessageType, payload: memoryview):
        PeerTCPClient._check_payload_len(message_id, payload, 0)

        if message_id == MessageType.choke:
            self._peer_choking = True
        elif message_id == MessageType.unchoke:
            self._peer_choking = False
        elif message_id == MessageType.interested:
            self._peer_interested = True
        elif message_id == MessageType.not_interested:
            self._peer_interested = False

    def _mark_as_owner(self, piece_index: int):
        self._piece_owned[piece_index] = True
        self._download_info.pieces[piece_index].owners.add(self._peer)
        if piece_index in self._download_info.interesting_pieces:
            self.am_interested = True

    def _handle_haves(self, message_id: MessageType, payload: memoryview):
        if message_id == MessageType.have:
            (index,) = struct.unpack('!I', cast(bytes, payload))
            self._mark_as_owner(index)
        elif message_id == MessageType.bitfield:
            piece_count = self._download_info.piece_count
            PeerTCPClient._check_payload_len(message_id, payload, int(ceil(piece_count / 8)))

            arr = bitarray(endian='big')
            arr.frombytes(payload.tobytes())
            for i in range(piece_count):
                if arr[i]:
                    self._mark_as_owner(i)
            for i in range(piece_count, len(arr)):
                if arr[i]:
                    raise ValueError('Spare bits in "bitfield" message must be zero')

        # if self._download_info.complete and self.is_seed():
        #     raise SeedError('A seed is disconnected because a download is complete')

    MAX_REQUEST_LENGTH = 2 ** 17

    def _check_position_range(self, request: BlockRequest):
        if request.piece_index < 0 or request.piece_index >= self._download_info.piece_count:
            raise IndexError('Piece index out of range')
        end_offset = request.piece_index * self._download_info.piece_length + \
            request.block_begin + request.block_length
        if (request.block_begin < 0 or request.block_begin + request.block_length > self._download_info.piece_length or
                end_offset > self._download_info.total_size):
            raise IndexError('Position in piece out of range')

    async def _handle_requests(self, message_id: MessageType, payload: memoryview):
        piece_index, begin, length = struct.unpack('!3I', cast(bytes, payload))
        request = BlockRequest(piece_index, begin, length)
        self._check_position_range(request)

        if message_id == MessageType.request:
            if length > PeerTCPClient.MAX_REQUEST_LENGTH:
                raise ValueError('Requested {} bytes, but the current policy allows to accept requests '
                                 'of not more than {} bytes'.format(length, PeerTCPClient.MAX_REQUEST_LENGTH))
            if (self._am_choking or not self._peer_interested or
                    not self._download_info.pieces[piece_index].downloaded):
                # If peer isn't interested but requesting, their peer_interested flag wasn't considered
                # when selecting who to unchoke, so we may be not ready to upload to them.
                # If requested piece is not downloaded yet, we shouldn't disconnect because our piece_downloaded flag
                # could be removed because of file corruption.
                return

            await self._send_block(request)
            await self.drain()
        elif message_id == MessageType.cancel:
            # Now we answer to a request immediately or reject and forget it,
            # so there's no need to handle cancel messages
            pass

    async def _handle_block(self, payload: memoryview):
        if not self._am_interested:
            # For example, we can be not interested in pieces from peers with big distrust rate
            return

        fmt = '!2I'
        piece_index, block_begin = struct.unpack_from(fmt, payload)
        block_data = memoryview(payload)[struct.calcsize(fmt):]
        block_length = len(block_data)
        request = BlockRequest(piece_index, block_begin, block_length)
        self._check_position_range(request)

        if not block_length:
            return

        async with self._file_structure.lock:
            # Manual lock acquiring guarantees that piece validation will not be performed between
            # condition checking and piece writing
            piece_info = self._download_info.pieces[piece_index]
            if piece_info.validating or piece_info.downloaded:
                return

            self._downloaded += block_length
            self._download_info.session_statistics.add_downloaded(self._peer, block_length)

            await self._file_structure.write(piece_index * self._download_info.piece_length + block_begin, block_data,
                                             acquire_lock=False)
            piece_info.mark_downloaded_blocks(self._peer, request)

            await asyncio.sleep(0.1)

    async def run(self):
        while True:
            message = await self._receive_message()
            await asyncio.sleep(0)

            if message is None:
                continue

            message_id, payload = message

            if message_id in (MessageType.choke, MessageType.unchoke,
                              MessageType.interested, MessageType.not_interested):
                self._handle_setting_states(message_id, payload)
            elif message_id in (MessageType.have, MessageType.bitfield):
                self._handle_haves(message_id, payload)
            elif message_id in (MessageType.request, MessageType.cancel):
                await self._handle_requests(message_id, payload)
            elif message_id == MessageType.piece:
                await self._handle_block(payload)
            elif message_id == MessageType.port:
                PeerTCPClient._check_payload_len(message_id, payload, 2)
                # TODO: Ignore or implement DHT

            await asyncio.sleep(0.1)

    def send_keep_alive(self):
        self._send_message(None)

    def _send_bitfield(self):
        if self._download_info.downloaded_piece_count:
            arr = bitarray([info.downloaded for info in self._download_info.pieces], endian='big')
            self._send_message(MessageType.bitfield, arr.tobytes())

    def send_have(self, piece_index: int):
        self._send_message(MessageType.have, struct.pack('!I', piece_index))

    def send_request(self, request: BlockRequest, cancel: bool=False):
        self._check_position_range(request)
        if not cancel:
            assert self._peer in self._download_info.pieces[request.piece_index].owners

        self._send_message(MessageType.request if not cancel else MessageType.cancel,
                           struct.pack('!3I', request.piece_index, request.block_begin, request.block_length))

    async def _send_block(self, request: BlockRequest):
        block = await self._file_structure.read(
            request.piece_index * self._download_info.piece_length + request.block_begin, request.block_length)
        await asyncio.sleep(0.05)
        # TODO: Maybe can handle cancels here

        self._send_message(MessageType.piece, struct.pack('!2I', request.piece_index, request.block_begin), block)

        self._uploaded += request.block_length
        self._download_info.session_statistics.add_uploaded(self._peer, request.block_length)

    async def drain(self):
        await asyncio.wait_for(self._writer.drain(), PeerTCPClient.WRITE_TIMEOUT)

    def close(self):
        if self._writer is not None:
            self._writer.close()

        self._connected = False
