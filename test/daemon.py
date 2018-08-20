import pytest
from galacteek.ipfs import asyncipfsd
import aioipfs

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
            p2pStreams=True,
            noBootstrap=True
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
            noBootstrap=True,
            pubsubEnable=False,
            p2pStreams=True
            )
    return daemon

@pytest.fixture()
def iclient(event_loop):
    return aioipfs.AsyncIPFS(port=apiport, loop=event_loop)

@pytest.fixture()
def iclient2(event_loop):
    return aioipfs.AsyncIPFS(port=apiport+10, loop=event_loop)

async def startDaemons(loop, d1, d2, execFn, *args, **kw):
    def cb2started(f):
        loop.create_task(execFn(*args, **kw))

    def cbstarted(f):
        d2.startedFuture.add_done_callback(cb2started)

    started = await d1.start()
    started = await d2.start()
    d1.startedFuture.add_done_callback(cbstarted)

def stopDaemons(d1, d2):
    d1.stop()
    d2.stop()
