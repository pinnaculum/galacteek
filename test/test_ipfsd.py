
import pytest

import tempfile
import time
import os
import json

import asyncio
import aioipfs

from galacteek.ipfs import asyncipfsd
from galacteek.ipfs import ipfsdconfig
from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.tunnel import *

apiport = 9005
gwport = 9081
swarmport = 9003

@pytest.fixture()
def ipfsdaemon(event_loop, tmpdir):
    dir = tmpdir.mkdir('ipfsdaemon')
    daemon = asyncipfsd.AsyncIPFSDaemon(dir,
            apiport=apiport,
            gatewayport=gwport,
            swarmport=swarmport,
            loop=event_loop,
            pubsubEnable=False,
            p2pStreams=True
            )
    return daemon

@pytest.fixture()
def ipfsdaemon2(event_loop, tmpdir):
    dir = tmpdir.mkdir('ipfsdaemon2')
    daemon = asyncipfsd.AsyncIPFSDaemon(dir,
            apiport=apiport+10,
            gatewayport=gwport+10,
            swarmport=swarmport+10,
            loop=event_loop,
            pubsubEnable=False,
            p2pStreams=True
            )
    return daemon

@pytest.fixture()
def iclient(event_loop):
    c = aioipfs.AsyncIPFS(port=apiport, loop=event_loop)
    return c

@pytest.fixture()
def ipfsop(iclient):
    return IPFSOperator(iclient, debug=True)

class EchoProtocol(asyncio.Protocol):
    def __init__(self, exitF):
        super().__init__()
        self.exitF = exitF
        self.msgCount = 0

    def connection_made(self, transport):
        print('Connection made')
        self.transport = transport
        self.transport.write('Hello'.encode())

    def data_received(self, data):
        self.msgCount += 1
        if self.msgCount < 5:
            self.transport.write(data)
        else:
            self.transport.close()

    def eof_received(self):
        pass

    def connection_lost(self, exc):
        self.exitF.set_result(True)

class TestIPFSD:
    @pytest.mark.asyncio
    async def test_basic(self, event_loop, ipfsdaemon, iclient, ipfsop):
        async def tests(op):
            id = await op.client.core.id()

            slashList = await op.filesList('/')
            async for r in op.client.add_json({'a': 123}):
                assert await op.filesLink(r, '/') == True

            await op.client.close()
            ipfsdaemon.stop()
            await asyncio.sleep(2)

        def cbstarted(f):
            event_loop.create_task(tests(ipfsop))

        started = await ipfsdaemon.start()
        ipfsdaemon.proto.startedFuture.add_done_callback(cbstarted)
        assert started == True
        await asyncio.wait([ipfsdaemon.exitFuture])

    @pytest.mark.asyncio
    async def test_tunnel(self, event_loop, ipfsdaemon, ipfsdaemon2,
            iclient, ipfsop):
        # Connect two nodes, create a P2P listener on the first one and make
        # the second node do the stream dial.

        iclient2 = aioipfs.AsyncIPFS(port=ipfsdaemon2.apiport, loop=event_loop)
        protoF = asyncio.Future()
        proto = EchoProtocol(protoF)
        port = 10010
        protoName = 'test'
        p2pL = P2PListener(iclient, protoName, ('127.0.0.1', port),
                lambda: proto)

        async def tcpEchoClient(portdest, message, loop):
            #reader, writer = await asyncio.open_connection('127.0.0.1', port)
            p = EchoProtocol(asyncio.Future())
            coro = loop.create_connection(
                    lambda: p,
                    '127.0.0.1', portdest)
            await coro

            await asyncio.sleep(2)

            encoded = message.encode()
            writer.write(encoded)
            data = await reader.read(100)
            print('Received: %r' % data.decode())
            assert data == encoded
            writer.close()

        async def createTunnel(op):
            id1 = await iclient.id()
            id2 = await iclient2.id()

            # Swarm connect the two nodes
            await iclient2.swarm.connect(
                '/ip4/127.0.0.1/tcp/{0}/ipfs/{1}'.format(
                    ipfsdaemon.swarmport, id1['ID']))

            peers2 = await iclient2.swarm.peers()
            listener = await p2pL.open()
            await iclient.p2p.listener_ls(headers=True)

            assert listener['Protocol'] == '/p2p/{}'.format(protoName)
            assert listener['Address'] == '/ip4/127.0.0.1/tcp/{}'.format(port)

            listenPort = port+1
            r = await iclient2.p2p.stream_dial(id1['ID'], 'test',
                    address='/ip4/127.0.0.1/tcp/{}'.format(listenPort))
            addr = r['Address']

            await tcpEchoClient(listenPort, 'Hello', event_loop)
            streams = await iclient2.p2p.stream_ls(headers=True)

            assert len(streams['Streams']) > 0
            print('streams', streams)
            stream = streams['Streams'].pop()

            assert stream['Protocol'] == '/p2p/{}'.format(protoName)
            assert stream['LocalPeer'] == id2['ID']
            assert stream['LocalAddress'] == '/ip4/127.0.0.1/tcp/{}'.format(
                    listenPort)
            assert stream['RemotePeer'] == id2['ID']

        def cb2started(f):
            event_loop.create_task(createTunnel(ipfsop))

        def cbstarted(f):
            ipfsdaemon2.startedFuture.add_done_callback(cb2started)

        ipfsdaemon.noBootstrap = True
        ipfsdaemon2.noBootstrap = True

        started = await ipfsdaemon.start()
        started = await ipfsdaemon2.start()

        ipfsdaemon.startedFuture.add_done_callback(cbstarted)

        await asyncio.wait([protoF])
        await p2pL.close()

        ipfsdaemon.stop()
        ipfsdaemon2.stop()

        await asyncio.wait([ipfsdaemon.exitFuture, ipfsdaemon2.exitFuture])

        await iclient.close()
        await iclient2.close()

@pytest.fixture()
def configD(tmpdir):
    return ipfsdconfig.getDefault()

class TestConfig:
    def test_default(self, configD):
        cfgStr = str(configD)
        assert 'API' in configD.c
        assert 'Bootstrap' in configD.c
