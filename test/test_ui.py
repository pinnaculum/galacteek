
# You need the pytest-qt plugin to run these tests

import pytest
import asyncio
import os.path

import tempfile
import time
import random

from PyQt5.QtCore import Qt

from galacteek.ui import dialogs
from galacteek.ui import mainui, ipfsview
from galacteek import application
from galacteek.appsettings import *
from galacteek.ipfs.wrappers import *
from galacteek.ipfs.ipfsops import *
from quamash import QEventLoop, QThreadExecutor

# CID lists
validcid0 = [
    'QmT1TPVjdZ9CRnqwyQ9WygDoRgRRibFrEyWufenu92SuUV',
    'QmT1TPajdu9CRnqwyQ9WygDoRgRRibFrEyWufenu92SuUV',
    'Qma1TPVjdZ9CRhqwyQ9Wev3oRgRRi5FrEyWufenu92SuUV',
    'Qmb2nxinR41eLpLr3FXquDV9kA2pxC6JAcJHs2aFYyeohP',
]

validcid1 = [
    'zb2rhnNU1uLw96nnLBXgrtRiJnKxLdU589S9kgCRt2FbALmYp',
    'zb2rhcrqjEudykbZ9eu245D4SoVxZFhBgiFGoGW7gGESgp67Z',
    'zb2rhYZ4An39RKsqpKU4D9Ux6Y5fZ7HeBP5KuxZKjt24dvB6P'
]

invalidcids = [
    'QmT1TPVjdZnu92SuUV',
    'QmT1TPajdu9CRnqwyQygfenu92Su',
    'Qma1TPVjdZ9CRhqwyQ9WevWufenuSuUV',
    '42',
    'knightswhosayni'
]

class TestCIDDialogs:
    # Valid and invalid CID lists
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

def makeAppNoDaemon():
    gApp = application.GalacteekApplication(profile='pytest-noipfsd', debug=True)
    loop = gApp.setupAsyncLoop()
    sManager = gApp.settingsMgr
    sManager.setFalse(CFG_SECTION_IPFSD, CFG_KEY_ENABLED)
    sManager.sync()
    gApp.updateIpfsClient()
    return gApp

def makeApp(profile='pytest-withipfsd'):
    r = random.Random()
    gApp = application.GalacteekApplication(profile=profile, debug=True)

    sManager = gApp.settingsMgr
    sManager.setTrue(CFG_SECTION_IPFSD, CFG_KEY_ENABLED)
    sManager.setSetting(CFG_SECTION_IPFSD, CFG_KEY_APIPORT,
            r.randint(15500, 15580))
    sManager.setSetting(CFG_SECTION_IPFSD, CFG_KEY_SWARMPORT,
            r.randint(15600, 15680))
    sManager.setSetting(CFG_SECTION_IPFSD, CFG_KEY_HTTPGWPORT,
            r.randint(15700, 15780))
    sManager.sync()
    loop = gApp.setupAsyncLoop()
    gApp.startIpfsDaemon()
    return gApp

@pytest.fixture
def gApp(qtbot, tmpdir):
    gApp = makeApp()
    sManager = gApp.settingsMgr
    sManager.setSetting(CFG_SECTION_BROWSER, CFG_KEY_DLPATH, str(tmpdir))
    sManager.sync()

    with qtbot.waitSignal(gApp.ipfsCtx.ipfsRepositoryReady):
        qtbot.wait(12000)

    yield gApp
    gApp.ipfsd.stop()
    gApp.stopIpfsServices()
    gApp.quit()

@pytest.fixture(scope='module')
def modApp():
    gApp = makeApp(profile='pytest-modapp')
    return gApp

class TestApp:
    @pytest.mark.asyncio
    async def test_appmain(self, qtbot, gApp, tmpdir, testfile1):
        """
        Test the application, running the GUI and testing all components
        """
        loop = gApp.getLoop()
        gApp.startPinner()

        def leftClick(w):
            qtbot.mouseClick(w, Qt.LeftButton)

        with loop:
            mainW = gApp.mainWindow

            async def openTabs():
                leftClick(mainW.ui.myFilesButton)
                leftClick(mainW.ui.openBrowserTabButton)
                leftClick(mainW.ui.bookmarksButton)
                leftClick(mainW.ui.manageKeysButton)
                leftClick(mainW.ui.writeNewDocumentButton)

                # Activate global pinning
                leftClick(mainW.ui.pinAllGlobalButton)
                await asyncio.sleep(1)

            async def browse():
                # Browse some hashes retrieved from the file manager's entry
                # cache, opening a tab for every tab
                await asyncio.sleep(1)
                filesW = mainW.findTabFileManager()
                cacheDirs = filesW.model.entryCache.getByType(1)
                hashes = list(cacheDirs.keys())

                for ohash in hashes[0:16]:
                    t = gApp.mainWindow.addBrowserTab()
                    t.browseIpfsHash(ohash)
                await asyncio.sleep(5)

            loop.run_until_complete(openTabs())
            loop.run_until_complete(browse())

    def test_ipfsview(self, qtbot, gApp, testFilesDocsAsync):
        loop = gApp.getLoop()
        view = ipfsview.IPFSHashViewToolBox(gApp.mainWindow, None)
        gApp.mainWindow.registerTab(view, '')

        @ipfsOpFn
        async def addAndView(ipfsop):
            root = await ipfsop.addPath(testFilesDocsAsync)
            view.viewHash(root['Hash'], autoOpenFolders=True)
            await asyncio.sleep(2)

        with loop:
            loop.run_until_complete(gApp.task(addAndView))

    @pytest.mark.parametrize('validcid0', validcid0)
    @pytest.mark.parametrize('validcid1', validcid1)
    @pytest.mark.parametrize('invalidcid', invalidcids)
    def test_clipboard(self, qtbot, modApp, validcid0, validcid1, invalidcid):
        def checkCorrect(valid, cid, path):
            item = modApp.clipTracker.getHistoryLatest()
            assert item['path'] == path
            return valid == True
        def checkIncorrect(valid, cid, path):
            return valid == False

        # Bare CIDv0
        with qtbot.waitSignal(modApp.clipTracker.clipboardHasIpfs, timeout=1000,
                check_params_cb=checkCorrect):
            modApp.setClipboardText(validcid0)

        # Bare CIDv1
        with qtbot.waitSignal(modApp.clipTracker.clipboardHasIpfs, timeout=1000,
                check_params_cb=checkCorrect):
            modApp.setClipboardText(validcid1)

        modApp.clipTracker.clearHistory()

        # /ipfs/CID
        with qtbot.waitSignal(modApp.clipTracker.clipboardHasIpfs, timeout=1000,
                check_params_cb=checkCorrect):
            modApp.setClipboardText(joinIpfs(validcid0))

        # fs:/ipfs/CID
        with qtbot.waitSignal(modApp.clipTracker.clipboardHasIpfs, timeout=1000,
                check_params_cb=checkCorrect):
            modApp.setClipboardText('fs:' + joinIpfs(validcid0))

        # ipfs:/ipfs/CID
        with qtbot.waitSignal(modApp.clipTracker.clipboardHasIpfs, timeout=1000,
                check_params_cb=checkCorrect):
            modApp.setClipboardText('ipfs:' + joinIpfs(validcid0))

        # /ipfs/CID/something
        with qtbot.waitSignal(modApp.clipTracker.clipboardHasIpfs, timeout=1000,
                check_params_cb=checkCorrect):
            path = os.path.join(joinIpfs(validcid0), 'some', 'garlic')
            modApp.setClipboardText(path)

        # /ipns/CID/something
        with qtbot.waitSignal(modApp.clipTracker.clipboardHasIpfs, timeout=1000,
                check_params_cb=checkCorrect):
            path = os.path.join(joinIpns(validcid0), 'share', 'the', 'wine')
            modApp.setClipboardText(path)

        with qtbot.waitSignal(modApp.clipTracker.clipboardHasIpfs, timeout=1000,
                check_params_cb=checkIncorrect):
            modApp.setClipboardText(invalidcid)

    def test_mediaplayer(self, qtbot, modApp):
        pass
