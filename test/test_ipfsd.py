
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

apiport = 9005
gwport = 9081
swarmport = 9003

@pytest.fixture()
def ipfsdaemon(event_loop, tmpdir):
    daemon = asyncipfsd.AsyncIPFSDaemon(tmpdir,
            apiport=apiport,
            gatewayport=gwport,
            swarmport=swarmport,
            loop=event_loop,
            pubsubEnable=False
            )
    return daemon

@pytest.fixture()
def iclient(event_loop):
    c = aioipfs.AsyncIPFS(port=apiport, loop=event_loop)
    return c

@pytest.fixture()
def ipfsop(iclient):
    return IPFSOperator(iclient, debug=True)

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
        await asyncio.sleep(15)

@pytest.fixture()
def configD(tmpdir):
    return ipfsdconfig.getDefault()

class TestConfig:
    def test_default(self, configD):
        cfgStr = str(configD)
        assert 'API' in configD.c
        assert 'Bootstrap' in configD.c
