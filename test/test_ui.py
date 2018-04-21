
# You need the pytest-qt plugin to run these tests

import pytest

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
