
import pytest

import tempfile
import random
import time
import os
import json

import asyncio
import aioipfs

from galacteek.ipfs import asyncipfsd
from galacteek.ipfs.ipfsops import *
from galacteek.core.ipfsmodel import *

apiport = 12000
gwport = 12080
swarmport = 9003

@pytest.fixture()
def ipfsdaemon(event_loop, tmpdir):
    daemon = asyncipfsd.AsyncIPFSDaemon(tmpdir,
            apiport=apiport,
            gatewayport=gwport,
            swarmport=swarmport,
            loop=event_loop,
            nobootstrap=True,
            pubsub_enable=False,
            debug=True,
            )
    return daemon

@pytest.fixture()
def iclient(event_loop):
    c = aioipfs.AsyncIPFS(port=apiport, loop=event_loop)
    return c

@pytest.fixture()
def ipfsop(iclient):
    return IPFSOperator(iclient, debug=True)

class TestModel:
    @pytest.mark.asyncio
    async def test_basic(self, event_loop, ipfsdaemon, iclient, ipfsop):
        model = mkIpfsModel()
        root = model.invisibleRootItem()

        async def tests(op):
            id = await op.client.core.id()
            r = random.Random()

            for i in range(0, 16):
                data = [str(r.randint(1, 128)) for j in range(0, 64) ]
                async for o in op.client.add_bytes(
                        ''.join(data).encode('ascii')):
                    model.registerIpfsObject(o, root)
                    print(o)

                    assert len(modelSearch(model, search=o['Hash'])) > 0

            await op.client.close()

            ipfsdaemon.stop()

        def cbstarted(f):
            event_loop.run_until_complete(tests(ipfsop))

        started = await ipfsdaemon.start()
        ipfsdaemon.proto.started_future.add_done_callback(cbstarted)
        await asyncio.sleep(5)
