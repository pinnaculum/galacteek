import pytest
import aioipfs
import asyncio
import time
import random
from concurrent.futures import ThreadPoolExecutor

from PyQt5.QtWidgets import QApplication

from galacteek.core import glogger
from galacteek.ipfs.ipfsops import IPFSOperator
from galacteek.ipfs.ipfsops import IPFSOpRegistry
from galacteek.ipfs import asyncipfsd
from galacteek.guientrypoint import buildArgsParser
from galacteek import application
from galacteek.appsettings import *

from . import mockipfsctx


glogger.basicConfig(level='DEBUG')


@pytest.fixture
def dbpath(tmpdir):
    return tmpdir.join('db.sqlite3')


@pytest.fixture
def mockApp(event_loop):
    app = QApplication([])
    app.loop = event_loop
    app.executor = ThreadPoolExecutor()

    return app


parser = buildArgsParser()


def makeApp(profile='pytest-withipfsd'):
    cmdArgs = parser.parse_args([])
    r = random.Random()
    gApp = application.GalacteekApplication(
        profile=profile,
        cmdArgs=cmdArgs)
    gApp.configure()

    sManager = gApp.settingsMgr
    sManager.setTrue(CFG_SECTION_IPFSD, CFG_KEY_ENABLED)
    sManager.setSetting(CFG_SECTION_IPFSD, CFG_KEY_APIPORT,
                        r.randint(15500, 15580))
    sManager.setSetting(CFG_SECTION_IPFSD, CFG_KEY_SWARMPORT,
                        r.randint(15600, 15680))
    sManager.setSetting(CFG_SECTION_IPFSD, CFG_KEY_HTTPGWPORT,
                        r.randint(15700, 15780))
    sManager.sync()
    return gApp


@pytest.fixture
def gApp(event_loop, qtbot, tmpdir):
    gApp = makeApp()
    sManager = gApp.settingsMgr
    sManager.setSetting(CFG_SECTION_BROWSER, CFG_KEY_DLPATH, str(tmpdir))
    sManager.sync()

    with qtbot.waitSignal(gApp.ipfsCtx._ipfsRepositoryReady, timeout=60000):
        print('Waiting for IPFS repository ...')

    time.sleep(1)
    yield gApp
    gApp.loop.run_until_complete(gApp.exitApp())


@pytest.fixture(scope='function')
def localipfsclient(event_loop):
    client = aioipfs.AsyncIPFS(loop=event_loop, host='127.0.0.1', port=5042)
    yield client


@pytest.mark.asyncio
@pytest.fixture(scope='function')
async def localipfsop(localipfsclient, mockApp):
    ctx = mockipfsctx.MockIPFSContext(mockApp)

    op = IPFSOperator(
        localipfsclient,
        ctx=ctx
    )

    IPFSOpRegistry.regDefault(op)
    await ctx.setup()
    yield op


apiport = 9005
gwport = 9081
swarmport = 9003


@pytest.fixture()
def ipfsdaemon(event_loop, tmpdir):
    dir = tmpdir.mkdir('ipfsdaemon')
    daemon = asyncipfsd.AsyncIPFSDaemon(str(dir),
                                        apiport=apiport,
                                        gatewayport=gwport,
                                        swarmport=swarmport,
                                        loop=event_loop,
                                        pubsubEnable=False,
                                        p2pStreams=True,
                                        noBootstrap=True,
                                        migrateRepo=True
                                        )
    return daemon


@pytest.fixture()
def ipfsdaemon2(event_loop, tmpdir):
    dir = tmpdir.mkdir('ipfsdaemon2')
    daemon = asyncipfsd.AsyncIPFSDaemon(str(dir),
                                        apiport=apiport + 10,
                                        gatewayport=gwport + 10,
                                        swarmport=swarmport + 10,
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
    return aioipfs.AsyncIPFS(port=apiport + 10, loop=event_loop)


@pytest.fixture()
def ipfsop(iclient):
    return IPFSOperator(iclient, debug=True)


async def startDaemons(loop, d1, d2, *args, **kw):
    started1 = await d1.start()
    started2 = await d2.start()

    assert started1 is True, started2 is True

    await asyncio.gather(*[
        d1.proto.eventStarted.wait(),
        d2.proto.eventStarted.wait()
    ])


def stopDaemons(d1, d2):
    d1.stop()
    d2.stop()
