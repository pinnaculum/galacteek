
# You need the pytest-qt plugin to run these tests

import pytest
import asyncio

import tempfile
import time

from PyQt5.QtCore import Qt

from galacteek.ui import dialogs

class TestCIDDialogs:
    # Valid and invalid CID lists
    @pytest.mark.parametrize('validcid0', [
        'QmT1TPVjdZ9CRnqwyQ9WygDoRgRRibFrEyWufenu92SuUV',
        'QmT1TPajdu9CRnqwyQ9WygDoRgRRibFrEyWufenu92SuUV',
        'Qma1TPVjdZ9CRhqwyQ9Wev3oRgRRi5FrEyWufenu92SuUV',
        'Qmb2nxinR41eLpLr3FXquDV9kA2pxC6JAcJHs2aFYyeohP',
    ])
    @pytest.mark.parametrize('validcid1', [
        'zb2rhnNU1uLw96nnLBXgrtRiJnKxLdU589S9kgCRt2FbALmYp',
	'zb2rhcrqjEudykbZ9eu245D4SoVxZFhBgiFGoGW7gGESgp67Z',
	'zb2rhYZ4An39RKsqpKU4D9Ux6Y5fZ7HeBP5KuxZKjt24dvB6P'
    ])
    @pytest.mark.parametrize('invalidcid', [
        'QmT1TPVjdZnu92SuUV',
        'QmT1TPajdu9CRnqwyQygfenu92Su',
        'Qma1TPVjdZ9CRhqwyQ9WevWufenuSuUV',
        '42',
        'knightswhosayni'
    ])
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

    @pytest.mark.parametrize('validcid0', [
        'QmT1TPVjdZ9CRnqwyQ9WygDoRgRRibFrEyWufenu92SuUV',
        'Qmb2nxinR41eLpLr3FXquDV9kA2pxC6JAcJHs2aFYyeohP',
    ])
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

from galacteek.ui import mainui
from galacteek import application
from galacteek.appsettings import *
from quamash import QEventLoop, QThreadExecutor

@pytest.fixture
def testfile1(tmpdir):
    filep = tmpdir.join('testfile1.txt')
    filep.write('POIEKJDOOOPIDMWOPIMPOWE()=ds129084bjcy')
    return filep

class TestApp:
    def test_appmain(self, qtbot, tmpdir, testfile1):
        """
        Test the application, running the GUI and testing all components
        """
        gApp = application.GalacteekApplication(profile='pytest', debug=True)
        loop = gApp.setupAsyncLoop()

        sManager = gApp.settingsMgr
        sManager.setFalse(CFG_SECTION_IPFSD, CFG_KEY_ENABLED)
        sManager.setSetting(CFG_SECTION_BROWSER, CFG_KEY_DLPATH, tmpdir)
        sManager.sync()
        gApp.updateIpfsClient()
        gApp.startPinner()

        def leftClick(w):
            qtbot.mouseClick(w, Qt.LeftButton)

        with loop:
            async def addSomeFiles(op):
                async for added in op.client.add(str(testfile1)):
                    await op.filesLink(added, '/galacteek/myfiles',
                        wrap_with_directory=True)

            mainW = gApp.mainWindow

            async def openTabs():
                leftClick(mainW.ui.myFilesButton)
                leftClick(mainW.ui.openBrowserTabButton)
                leftClick(mainW.ui.bookmarksButton)
                leftClick(mainW.ui.manageKeysButton)
                leftClick(mainW.ui.writeNewDocumentButton)

                # Activate global pinning
                leftClick(mainW.ui.pinAllGlobalButton)

            async def browse():
                # Browse some hashes retrieved from the file manager's entry
                # cache, opening a tab for every tab
                await asyncio.sleep(1)
                filesW = mainW.findTabMyFiles()
                cacheDirs = filesW.entryCache.getByType(1)
                hashes = list(cacheDirs.keys())

                for ohash in hashes[0:16]:
                    t = gApp.mainWindow.addBrowserTab()
                    t.browseIpfsHash(ohash)
                await asyncio.sleep(3)

                gApp.stopIpfsServices()

            loop.run_until_complete(openTabs())
            loop.run_until_complete(browse())
