
# You need the pytest-qt plugin to run these tests

import pytest
import asyncio
import os.path

import tempfile
import time
import random

from PyQt5.QtCore import Qt

from .cidtest import *

from galacteek.ui import dialogs
from galacteek.ui import mainui, ipfsview
from galacteek import application
from galacteek.appsettings import *
from galacteek.ipfs.wrappers import *
from galacteek.ipfs.ipfsops import *

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
    loop = gApp.setupAsyncLoop()

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
#@pytest.mark.asyncio
def gApp(qtbot, tmpdir):
    gApp = makeApp()
    sManager = gApp.settingsMgr
    sManager.setSetting(CFG_SECTION_BROWSER, CFG_KEY_DLPATH, str(tmpdir))
    sManager.sync()

    gApp.startIpfsDaemon()
    with qtbot.waitSignal(gApp.ipfsCtx.ipfsRepositoryReady, timeout=20000):
        print('Waiting for IPFS repository ...')

    yield gApp

    gApp.ipfsd.stop()
    gApp.stopIpfsServices()
    gApp.quit()

@pytest.fixture(scope='module')
def modApp():
    return makeApp(profile='pytest-modapp')

class TestApp:
    @pytest.mark.asyncio
    async def test_appmain(self, qtbot, gApp, tmpdir, testfile1):
        """
        Test the application, running the GUI and testing all components
        """
        loop = gApp.loop

        def leftClick(w):
            qtbot.mouseClick(w, Qt.LeftButton)

        with loop:
            mainW = gApp.mainWindow

            async def openTabs():
                leftClick(mainW.ui.myFilesButton)
                leftClick(mainW.ui.openBrowserTabButton)
                leftClick(mainW.ui.hashmarksButton)
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

    @pytest.mark.asyncio
    async def test_ipfsview(self, qtbot, gApp, testFilesDocsAsync):
        loop = gApp.loop

        @ipfsOpFn
        async def addAndView(ipfsop):
            view = ipfsview.IPFSHashExplorerToolBox(gApp.mainWindow, None)
            gApp.mainWindow.registerTab(view, '')
            root = await ipfsop.addPath(testFilesDocsAsync)
            view.viewHash(root['Hash'], autoOpenFolders=True)
            await ipfsop.sleep(2)

        with loop:
            loop.run_until_complete(addAndView())

    @pytest.mark.parametrize('validcid0', validcid0)
    @pytest.mark.parametrize('validcid1', validcid1)
    @pytest.mark.parametrize('validcidb32', validcidb32)
    @pytest.mark.parametrize('invalidcid', invalidcids)
    def test_clipboard(self, qtbot, modApp, validcid0, validcid1, validcidb32, invalidcid):
        def checkCorrect(valid, cid, path):
            item = modApp.clipTracker.getHistoryLatest()
            assert item['path'] == path
            return valid == True
        def checkIncorrect(valid, cid, path):
            return valid == False

        def waitCorrect(cb=checkCorrect, timeout=1000):
            return qtbot.waitSignal(modApp.clipTracker.clipboardHasIpfs,
                timeout=timeout, check_params_cb=cb)

        def waitIncorrect(cb=checkIncorrect, timeout=1000):
            return qtbot.waitSignal(modApp.clipTracker.clipboardHasIpfs,
                timeout=timeout, check_params_cb=cb)

        modApp.clipTracker.clearHistory()

        # Bare CIDv0
        with waitCorrect():
            modApp.setClipboardText(validcid0)

        # Multiline CIDs
        with waitCorrect():
            modApp.setClipboardText('\n'.join([
                validcid0,
                '++' * 30,
                validcid1
            ]))

        # Bare CIDv1
        with waitCorrect():
            modApp.setClipboardText(validcid1)

        modApp.clipTracker.clearHistory()

        # /ipfs/CID
        with waitCorrect():
            modApp.setClipboardText(joinIpfs(validcid0))

        # /ipfs/CID with leading and trailing spaces
        with waitCorrect():
            modApp.setClipboardText('      {}   '.format(joinIpfs(validcid0)))

        # http(s)://ipfs.io/ipfs/CID
        with waitCorrect():
            modApp.setClipboardText('https://ipfs.io{}'.format(joinIpfs(validcid0)))

        # http(s)://localhost:8080/ipfs/CID
        with waitCorrect():
            modApp.setClipboardText('http://localhost:8080{}'.format(joinIpfs(validcid0)))

        # http(s)://localhost:8080/ipns/CID
        with waitCorrect():
            modApp.setClipboardText('http://localhost:8080{}'.format(joinIpns(validcid1)))

        # multiple lines with /ipfs/CID, will only register the first match
        with waitCorrect():
            modApp.setClipboardText('\n'.join([
                joinIpfs(validcid0),
                joinIpfs(validcid1),
            ]))

        # fs:/ipfs/CID
        with waitCorrect():
            modApp.setClipboardText('fs:' + joinIpfs(validcid0))

        # ipfs:/ipfs/CID
        with waitCorrect():
            modApp.setClipboardText('ipfs:' + joinIpfs(validcid0))

        # /ipfs/CID/something
        with waitCorrect():
            path = os.path.join(joinIpfs(validcid0), 'some', 'garlic')
            modApp.setClipboardText(path)

        # /ipns/CID/something
        with waitCorrect():
            path = os.path.join(joinIpns(validcid0), 'share', 'the', 'wine')
            modApp.setClipboardText(path)

        # Invalid CID input
        with waitIncorrect():
            modApp.setClipboardText(invalidcid)

    def test_mediaplayer(self, qtbot, modApp):
        pass
