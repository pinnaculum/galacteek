
import sys
import json

import aioipfs
import asyncio
import socket

from galacteek import log
from galacteek.ipfs.wrappers import *
from galacteek.ipfs.multi import multiAddrTcp4

class P2PProtocol(asyncio.Protocol):
    def __init__(self):
        super(P2PProtocol, self).__init__()

        self.exitFuture = asyncio.Future()
        self.eofReceived = False

    def connection_made(self, transport):
        log.debug('Connection made')
        self.transport = transport

    def data_received(self, data):
        log.debug('Data received {}'.format(data))

    def eof_received(self):
        self.eofReceived = True

    def connection_lost(self, exc):
        self.exitFuture.set_result(True)

class P2PListener(object):
    """
    IPFS P2P listener class

    :param client: AsyncIPFS client
    :param str protocol: protocol name
    :param tuple address: address to listen on
    :param factory: protocol factory
    """

    def __init__(self, client, protocol, address, factory, loop=None):
        self.client = client
        self._protocol = protocol
        self._address = address
        self._factory = factory
        self._server = None

        self.loop = loop if loop else asyncio.get_event_loop()

    @property
    def server(self):
        return self._server

    @property
    def protocol(self):
        return self._protocol

    @property
    def address(self):
        return self._address

    @property
    def protocolFactory(self):
        return self._factory

    async def open(self):
        listenAddress = '/ip4/{addr}/tcp/{port}'.format(
            addr=self.address[0],
            port=self.address[1]
        )

        try:
            addr = await self.client.p2p.listener_open(
                self.protocol, listenAddress)
        except aioipfs.APIError as exc:
            # P2P not enabled or some other reason
            return None
        else:
            # Now that the listener is registered, create the server socket
            # and return the listener's address
            if await self.createServer():
                return addr

    async def createServer(self):
        host = self.address[0]
        for port in range(self.address[1], self.address[1]+64):
            log.debug('P2PListener: trying port {0}'.format(port))

            try:
                srv = await self.loop.create_server(self.protocolFactory,
                        host, port)
                if srv:
                    self._server = srv
                    return True
            except:
                continue


    async def close(self):
        log.debug('P2PListener: closing {0}'.format(self.protocol))
        ret = await self.client.p2p.listener_close(self.protocol)

        if self._server:
            self._server.close()
            await self._server.wait_closed()

@ipfsOpFn
async def dial(op, peer, protocol, address=None):
    loop = asyncio.get_event_loop()
    log.debug('Stream dial {0} {1}'.format(peer, protocol))
    resp = await op.client.p2p.stream_dial(peer, protocol,
            address=address)
    if resp:
        maddr = resp.get('Address', None)
        if not maddr:
            return

        ipaddr, port = multiAddrTcp4(maddr)

        if ipaddr is None or port is 0:
            return

        reader, writer = await loop.create_connection(
                lambda: P2PProtocol(), '127.0.0.1', port)
