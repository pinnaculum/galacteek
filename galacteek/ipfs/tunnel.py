
import sys
import json

import aioipfs
import asyncio
import socket

class P2PProtocol(asyncio.Protocol):
    def __init__(self):
        super(P2PProtocol, self).__init__()

        self.exitFuture = asyncio.Future()
        self.eofReceived = False

    def connection_made(self, transport):
        self.transport = transport

    def data_received(self, data):
        self.transport.write(data)

    def eof_received(self):
        self.eofReceived = True

    def connection_lost(self, exc):
        self.exitFuture.set_result(True)

class P2PListener(object):
    """ IPFS P2P listener class """

    def __init__(self, client, protocol, address, factory):
        self.client = client
        self._protocol = protocol
        self._address = address
        self._factory = factory
        self._server = None

        self.loop = asyncio.get_event_loop()

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
        except aioipfs.APIException as exc:
            # P2P not enabled or some other reason
            return None
        else:
            # Now that the listener is registered, create the server socket
            # and return the listener's address
            await self.createServer()
            return addr

    async def createServer(self):
        self._server = await self.loop.create_server(self.protocolFactory,
            self.address[0], self.address[1])

    async def close(self):
        ret = await self.client.p2p.listener_close(self.protocol)

        if self._server:
            self._server.close()
            await self._server.wait_closed()
