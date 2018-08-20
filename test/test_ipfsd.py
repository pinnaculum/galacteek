
import pytest

import tempfile
import time
import os
import json

import asyncio
import aioipfs

from PyQt5.QtCore import QObject, pyqtSignal

from galacteek.ipfs import asyncipfsd
from galacteek.ipfs import ipfsdconfig
from galacteek.core.ipfsmarks import *
from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.tunnel import *
from galacteek.ipfs.pubsub import *

from .daemon import *

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
            iclient, iclient2, ipfsop):
        # Connect two nodes, create a P2P listener on the first one and make
        # the second node do the stream dial.

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

        await startDaemons(event_loop, ipfsdaemon, ipfsdaemon2, createTunnel,
                ipfsop)

        await asyncio.wait([protoF])
        await p2pL.close()

        ipfsdaemon.stop()
        ipfsdaemon2.stop()

        await asyncio.wait([ipfsdaemon.exitFuture, ipfsdaemon2.exitFuture])

        await iclient.close()
        await iclient2.close()

    @pytest.mark.parametrize('hashmarkpath',
            ['/ipfs/QmT1TPVjdZ9CRnqwyQ9WygDoRgRRibFrEyWufenu92SuUV'])
    @pytest.mark.asyncio
    async def test_hashmarks_exchange(self, event_loop, ipfsdaemon, ipfsdaemon2,
            iclient, iclient2, ipfsop, tmpdir, hashmarkpath):
        ipfsdaemon.pubsubEnable = True
        ipfsdaemon2.pubsubEnable = True

        async def exchange():
            marks = IPFSMarks(str(tmpdir.join('marks1.json')))
            marksNet = IPFSMarks(str(tmpdir.join('marks1net.json')))
            marks2 = IPFSMarks(str(tmpdir.join('marks2.json')))
            marks2Net = IPFSMarks(str(tmpdir.join('marks2net.json')))

            m1 = IPFSHashMark.make(hashmarkpath, share=True,
                    description='a shared hashmark',
                    title='stuff')

            def rx1(m):
                print('RX1 >', m)
            def rx2(m):
                print('RX2 >>', m)

            def marksReceived(count):
                assert count == 1
                searchR = marks2Net.search(hashmarkpath)
                assert  searchR[0] == hashmarkpath

                exchanger.stop()
                exchanger2.stop()

                stopDaemons(ipfsdaemon, ipfsdaemon2)

            ctx = Ctx()
            exchanger = HashmarksExchanger(iclient, event_loop, ctx, marks,
                    marksNet)
            exchanger.start()
            ctx.pubsubMessageRx.connect(rx1)

            ctx2 = Ctx()
            ctx2.pubsubMessageRx.connect(rx2)
            ctx2.pubsubMarksReceived.connect(marksReceived)
            exchanger2 = HashmarksExchanger(iclient2, event_loop, ctx2, marks2,
                    marks2Net)
            exchanger2.start()
            await asyncio.sleep(1)
            marks.insertMark(m1, 'shared/hashmarks')

        await startDaemons(event_loop, ipfsdaemon, ipfsdaemon2, exchange)
        await asyncio.wait([ipfsdaemon.exitFuture, ipfsdaemon2.exitFuture])

        await iclient.close()
        await iclient2.close()

class Ctx(QObject):
    pubsubMessageRx = pyqtSignal(dict)
    pubsubMessageTx = pyqtSignal()
    pubsubMarksReceived = pyqtSignal(int)

class Exchanger(PubsubListener):
    def __init__(self, client, loop, ipfsCtx):
        super().__init__(client, loop, ipfsCtx, topic='test')

@pytest.fixture()
def configD(tmpdir):
    return ipfsdconfig.getDefault()

class TestConfig:
    def test_default(self, configD):
        cfgStr = str(configD)
        assert 'API' in configD.c
        assert 'Bootstrap' in configD.c
