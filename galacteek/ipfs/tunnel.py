import aioipfs
import asyncio

from galacteek import log
from galacteek.ipfs.wrappers import *  # noqa
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

    def __init__(self, client, protocol, addressRange, factory, loop=None):
        self.client = client
        self._protocol = protocol
        self._addressRange = addressRange
        self._listenMultiAddr = None
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
    def addressRange(self):
        return self._addressRange

    @property
    def listenMultiAddr(self):
        return self._listenMultiAddr

    @listenMultiAddr.setter
    def listenMultiAddr(self, v):
        log.debug('Listening multiaddr {}'.format(v))
        self._listenMultiAddr = v

    @property
    def protocolFactory(self):
        return self._factory

    async def open(self):
        addrSrv = await self.createServer(
                host=self.addressRange[0],
                portRange=self.addressRange[1]
        )

        if addrSrv is None:
            return None

        listenAddress = '/ip4/{addr}/tcp/{port}'.format(
            addr=addrSrv[0],
            port=addrSrv[1]
        )

        try:
            addr = await self.client.p2p.listener_open(
                self.protocol, listenAddress)
        except aioipfs.APIError:
            # P2P not enabled or some other reason
            log.debug('P2PListener: creating listener failed')
            return None
        else:
            # Verify the multiaddr
            lAddr = addr.get('Address', None)
            if lAddr is None:  # wtf
                return None

            ipAddr, port = multiAddrTcp4(lAddr)

            if ipAddr == addrSrv[0] and port == addrSrv[1]:
                self.listenMultiAddr = lAddr
                return self.listenMultiAddr

    async def createServer(self, host='127.0.0.1', portRange=[]):
        for port in portRange:
            log.debug('P2PListener: trying port {0}'.format(port))

            try:
                srv = await self.loop.create_server(self.protocolFactory,
                                                    host, port)
                if srv:
                    self._server = srv
                    return (host, port)
            except BaseException:
                continue
        return None

    async def close(self):
        log.debug('P2PListener: closing {0}'.format(self.protocol))
        await self.client.p2p.listener_close(self.protocol)

        if self._server:
            self._server.close()
            await self._server.wait_closed()


class P2PTunnelsManager:
    @ipfsOp
    async def getListeners(self, op):
        try:
            listeners = await op.client.p2p.listener_ls(headers=True)
        except aioipfs.APIError:
            return None
        else:
            return listeners['Listeners']

    @ipfsOp
    async def streams(self, op):
        try:
            return await op.client.p2p.stream_ls(headers=True)
        except aioipfs.APIError:
            return None


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
