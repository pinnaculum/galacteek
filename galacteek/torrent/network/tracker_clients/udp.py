import asyncio
import logging
import random
import struct
import urllib.parse
from enum import Enum
from typing import Optional

from galacteek.torrent.models import DownloadInfo
from galacteek.torrent.network.tracker_clients.base import BaseTrackerClient, EventType, TrackerError, \
    parse_compact_peers_list


__all__ = ['UDPTrackerClient']


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class DatagramReaderProtocol:
    """Implements missing stream API for UDP with asyncio.
    Combines analogs for StreamReaderProtocol and StreamReader classes."""

    def __init__(self):
        self._buffer = bytearray()
        self._waiter = None     # type: Optional[asyncio.Future]
        self._connection_lost = False
        self._exception = None  # type: Exception

    def connection_made(self, transport: asyncio.DatagramTransport):
        pass

    async def recv(self) -> bytes:
        if self._waiter is not None:
            raise RuntimeError('Another coroutine is already waiting for incoming data')

        if self._exception is None and not self._connection_lost and not self._buffer:
            self._waiter = asyncio.Future()
            try:
                await self._waiter
            finally:
                self._waiter = None
        if self._exception is not None:
            exc = self._exception
            self._exception = None
            raise exc
        if self._connection_lost:
            raise ConnectionResetError('Connection lost')

        buffer = self._buffer
        self._buffer = bytearray()
        return buffer

    def _wakeup_waiter(self):
        if self._waiter is not None:
            self._waiter.set_result(None)

    def datagram_received(self, data: bytes, addr: tuple):
        self._buffer.extend(data)
        self._wakeup_waiter()

    def error_received(self, exc: Exception):
        self._exception = exc
        self._wakeup_waiter()

    def connection_lost(self, exc: Exception):
        self._connection_lost = True
        self._exception = exc
        self._wakeup_waiter()


class ActionType(Enum):
    connect = 0
    announce = 1
    scrape = 2  # TODO: not implemented yet
    error = 3


def pack(*data) -> bytes:
    assert len(data) % 2 == 0

    common_format = '!' + ''.join(fmt for fmt in data[::2])
    values = [elem for elem in data[1::2]]
    return struct.pack(common_format, *values)


class UDPTrackerClient(BaseTrackerClient):
    def __init__(self, url: urllib.parse.ParseResult, download_info: DownloadInfo, our_peer_id: bytes,
                 *, loop: asyncio.AbstractEventLoop=None):
        super().__init__(download_info, our_peer_id)
        if url.scheme != 'udp':
            raise ValueError('TrackerUDPClient expects announce_url with UDP protocol')
        self._host = url.hostname
        self._port = url.port

        self._loop = asyncio.get_event_loop() if loop is None else loop

        self._key = random.randint(0, 2 ** 32 - 1)  # TODO: maybe implement the same key in HTTPTrackerClient
        # > An additional client identification mechanism that is not shared with any peers.
        # > It is intended to allow a client to prove their identity should their IP address change.
        # Source: https://wiki.theory.org/BitTorrentSpecification#Tracker_Request_Parameters

    MAGIC_CONNECTION_ID = 0x41727101980

    RESPONSE_HEADER_FMT = '!II'
    RESPONSE_HEADER_LEN = struct.calcsize(RESPONSE_HEADER_FMT)

    @staticmethod
    def _check_response(response: bytes, expected_transaction_id: bytes, expected_action: ActionType):
        actual_action, actual_transaction_id = struct.unpack_from(UDPTrackerClient.RESPONSE_HEADER_FMT, response)

        if actual_transaction_id != expected_transaction_id:
            raise ValueError('Unexpected transaction ID')
        # TODO: lock for announcements to one server?
        #       Or both sockets will receive data and one will just skip a wrong packet?

        actual_action = ActionType(actual_action)
        if actual_action == ActionType.error:
            message = response[UDPTrackerClient.RESPONSE_HEADER_LEN:]
            raise TrackerError(message.decode())
        if actual_action != expected_action:
            raise ValueError('Unexpected action ID (expected {}, got {})'.format(
                expected_action.name, actual_action.name))

    REQUEST_TIMEOUT = 12
    # FIXME: Repeat requests as described in BEP 0015, but remember that we may have other trackers in announce-list

    async def announce(self, server_port: int, event: EventType):
        transport, protocol = await self._loop.create_datagram_endpoint(
            DatagramReaderProtocol, remote_addr=(self._host, self._port))

        try:
            transaction_id = random.randint(0, 2 ** 32 - 1)
            request = pack(
                'Q', UDPTrackerClient.MAGIC_CONNECTION_ID,
                'I', ActionType.connect.value,
                'I', transaction_id,
            )
            transport.sendto(request)

            response = await asyncio.wait_for(protocol.recv(), UDPTrackerClient.REQUEST_TIMEOUT)
            UDPTrackerClient._check_response(response, transaction_id, ActionType.connect)
            (connection_id,) = struct.unpack_from('!Q', response, UDPTrackerClient.RESPONSE_HEADER_LEN)

            request = pack(
                'Q', connection_id,
                'I', ActionType.announce.value,
                'I', transaction_id,
                '20s', self._download_info.info_hash,
                '20s', self._our_peer_id,
                'Q', self._statistics.total_downloaded,
                'Q', self._download_info.bytes_left,
                'Q', self._statistics.total_uploaded,
                'I', event.value,
                'I', 0,  # IP address: default
                'I', self._key,  # Key
                'i', -1,  # numwant: default
                'H', server_port,
            )
            assert len(request) == 98
            transport.sendto(request)

            response = await asyncio.wait_for(protocol.recv(), UDPTrackerClient.REQUEST_TIMEOUT)
            UDPTrackerClient._check_response(response, transaction_id, ActionType.announce)
            fmt = '!3I'
            self.interval, self.leech_count, self.seed_count = struct.unpack_from(
                fmt, response, UDPTrackerClient.RESPONSE_HEADER_LEN)
            self.min_interval = self.interval

            compact_peer_list = response[UDPTrackerClient.RESPONSE_HEADER_LEN + struct.calcsize(fmt):]
            self._peers = parse_compact_peers_list(compact_peer_list)
        finally:
            transport.close()
