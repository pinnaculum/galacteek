import pytest
import os.path

import time
import random

from PyQt5.QtCore import Qt

from ..cidtest import *

from galacteek.guientrypoint import buildArgsParser
from galacteek.ui import dialogs
from galacteek import application
from galacteek.appsettings import *
from galacteek.ipfs.wrappers import *
from galacteek.ipfs.ipfsops import *


@pytest.fixture
def testfile1(tmpdir):
    filep = tmpdir.join('testfile1.txt')
    filep.write('POIEKJDOOOPIDMWOPIMPOWE()=ds129084bjcy')
    return filep


@pytest.fixture
def dirTestFiles(pytestconfig):
    return os.path.join(pytestconfig.rootdir,
                        'test', 'testfiles')


@pytest.fixture
def testFilesDocsAsync(dirTestFiles):
    return os.path.join(dirTestFiles, 'docs-asyncio')


parser = buildArgsParser()


def makeAppNoDaemon():
    cmdArgs = parser.parse_args([])

    gApp = application.GalacteekApplication(
        profile='pytest-noipfsd', debug=True,
        cmdArgs=cmdArgs)
    sManager = gApp.settingsMgr
    sManager.setFalse(CFG_SECTION_IPFSD, CFG_KEY_ENABLED)
    sManager.sync()
    gApp.updateIpfsClient()
    return gApp


def makeApp(profile='pytest-withipfsd'):
    cmdArgs = parser.parse_args([])
    r = random.Random()
    gApp = application.GalacteekApplication(
        profile=profile,
        cmdArgs=cmdArgs)

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


@pytest.fixture(scope='module')
def modApp():
    return makeApp(profile='pytest-modapp')


def leftClick(qtbot, w):
    qtbot.mouseClick(w, Qt.LeftButton)


class TestApp:
    @pytest.mark.asyncio
    async def test_appmain(self, qtbot, gApp, tmpdir, testfile1):
        mainW = gApp.mainWindow

        async def openTabs():
            leftClick(qtbot, mainW.fileManagerButton)
            leftClick(qtbot, mainW.browseButton)
            leftClick(qtbot, mainW.hashmarkMgrButton)

        await openTabs()


class TestCIDDialogs:
    @pytest.mark.parametrize('validcid0', validcid0)
    @pytest.mark.parametrize('validcid1', validcid1)
    @pytest.mark.parametrize('invalidcid', invalidcids)
    def test_singlecidinput(self, qtbot, validcid0, validcid1, invalidcid):
        dlg = dialogs.IPFSCIDInputDialog()
        qtbot.addWidget(dlg)

        self.cidInput(qtbot, dlg, validcid0)
        assert dlg.validCid is True
        assert dlg.ui.validity.text() == 'Valid CID version 0'

        dlg.clearCID()
        self.cidInput(qtbot, dlg, validcid1)
        assert dlg.validCid is True
        assert dlg.ui.validity.text() == 'Valid CID version 1'

        dlg.clearCID()
        self.cidInput(qtbot, dlg, invalidcid)
        assert dlg.validCid is False

    @pytest.mark.parametrize('validcid0', validcid0)
    def test_mulcidinput(self, qtbot, validcid0):
        dlg = dialogs.IPFSMultipleCIDInputDialog()
        qtbot.addWidget(dlg)

        self.cidInput(qtbot, dlg, validcid0)
        qtbot.mouseClick(dlg.ui.addCidButton, Qt.LeftButton)

        cidList = dlg.getCIDs()
        assert len(cidList) == 1
        assert cidList.pop() == validcid0

    def cidInput(self, qtbot, dlg, cid):
        # Manually input the CID character by character
        # The whole unit test is a bit cpu-intensive since the dialog will
        # check CID's validity on every char input but hey ..
        for char in cid:
            qtbot.keyPress(dlg.ui.cid, char)
