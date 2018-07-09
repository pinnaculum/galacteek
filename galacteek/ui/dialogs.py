
import time

from PyQt5.QtWidgets import (QWidget, QApplication,
        QDialog, QLabel, QTextEdit, QPushButton, QMessageBox)

from PyQt5.QtCore import QUrl, Qt, pyqtSlot, QCoreApplication
from PyQt5.QtGui import QClipboard

from galacteek.core.ipfsmarks import *
from galacteek.ipfs import cidhelpers

from . import ui_addkeydialog, ui_addhashmarkdialog
from . import ui_addfeeddialog
from . import ui_ipfscidinputdialog, ui_ipfsmultiplecidinputdialog
from . import ui_donatedialog

import mimetypes

def boldLabelStyle():
    return 'QLabel { font-weight: bold; }'

class AddHashmarkDialog(QDialog):
    def __init__(self, marks, resource, title, stats, parent=None):
        super().__init__(parent)

        self.ipfsResource = resource
        self.marks = marks
        self.stats = stats if stats else {}

        self.ui = ui_addhashmarkdialog.Ui_AddHashmarkDialog()
        self.ui.setupUi(self)
        self.ui.resourceLabel.setText(self.ipfsResource)
        self.ui.resourceLabel.setStyleSheet(boldLabelStyle())
        self.ui.newCategory.textChanged.connect(self.onNewCatChanged)
        self.ui.title.setText(title)

        for cat in self.marks.getCategories():
            self.ui.category.addItem(cat)

    def onNewCatChanged(self, text):
        if len(text) > 0:
            self.ui.category.setEnabled(False)
        else:
            self.ui.category.setEnabled(True)

    def accept(self):
        share = self.ui.share.isChecked()
        newCat = self.ui.newCategory.text()

        if len(newCat) > 0:
            category = newCat
        else:
            category = self.ui.category.currentText()

        # Basic content-type guessing for now
        ctype = mimetypes.guess_type(self.ipfsResource)[0] or None

        mark = IPFSMarkData.make(self.ipfsResource,
            title=self.ui.title.text(),
            share=share,
            comment=self.ui.comment.text(),
            tags=self.ui.tags.text().split(),
            datasize=self.stats.get('DataSize', None),
            cumulativesize=self.stats.get('CumulativeSize', None),
            numlinks=self.stats.get('NumLinks', None),
            ctype=ctype
        )

        self.marks.insertMark(mark, category)
        self.done(0)

class AddFeedDialog(QDialog):
    def __init__(self, marks, resource, parent=None):
        super().__init__(parent)

        self.marks = marks
        self.ipfsResource = resource

        self.ui = ui_addfeeddialog.Ui_AddFeedDialog()
        self.ui.setupUi(self)
        self.ui.resourceLabel.setText(self.ipfsResource)
        self.ui.resourceLabel.setStyleSheet(boldLabelStyle())

    def accept(self):
        share = self.ui.share.isChecked()

        self.marks.follow(self.ipfsResource, self.ui.feedName.text(),
            resolveevery=self.ui.resolve.value(),
            share=share)
        self.done(0)

class IPFSCIDInputDialog(QDialog):
    """ Dialog for IPFS CID input and validation """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.validCid = False
        self.ui = ui_ipfscidinputdialog.Ui_CIDInputDialog()
        self.ui.setupUi(self)
        self.ui.validity.setStyleSheet(boldLabelStyle())
        self.ui.cid.textChanged.connect(self.onCIDChanged)
        self.ui.clearButton.clicked.connect(self.onClearCID)

    def onClearCID(self):
        self.clearCID()

    def clearCID(self):
        """ Clears the CID input text """
        self.ui.cid.clear()

    def onCIDChanged(self, text):
        """
        When the CID input text changes we verify if it's a valid CID and
        update the validity label
        """
        if cidhelpers.cidValid(text):
            cid = self.getCID()
            if cid:
                self.ui.validity.setText(
                    'Valid CID version {}'.format(cid.version))
                self.validCid = True
            else:
                # Unlikely
                self.ui.validity.setText('Unknown CID type')
                self.validCid = False
        else:
            self.ui.validity.setText('Invalid CID')
            self.validCid = False

    def getHash(self):
        """ Returns the hash corresponding to the input, if valid """
        cid = self.getCID()
        if cid:
            return str(cid)

    def getCID(self):
        """ Returns the CID object corresponding to the input """
        try:
            return cidhelpers.getCID(self.ui.cid.text())
        except:
            return None

    def accept(self):
        if self.validCid is True:
            self.done(1)

class IPFSMultipleCIDInputDialog(QDialog):
    """ Dialog for multiple IPFS CID input """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.validCid = False
        self.ui = ui_ipfsmultiplecidinputdialog.Ui_MultipleCIDInputDialog()
        self.ui.setupUi(self)
        self.ui.validity.setStyleSheet(boldLabelStyle())
        self.ui.cid.textChanged.connect(self.onCIDChanged)
        self.ui.addCidButton.clicked.connect(self.onAddCID)

    def onAddCID(self):
        if self.validCid:
            self.ui.cidList.addItem(self.ui.cid.text())
            self.ui.cid.clear()

    def onCIDChanged(self, text):
        if cidhelpers.cidValid(text):
            self.ui.validity.setText('Valid CID')
            self.validCid = True
        else:
            self.ui.validity.setText('Invalid CID')
            self.validCid = False

    def getCIDs(self):
        cids = []
        for idx in range(0, self.ui.cidList.count()):
            item = self.ui.cidList.item(idx)
            cids.append(item.text())
        return cids

    def accept(self):
        self.done(1)

class DonateDialog(QDialog):
    def __init__(self, moneroAddr, bcAddr, parent=None):
        super().__init__(parent)

        self.ui = ui_donatedialog.Ui_DonateDialog()
        self.ui.setupUi(self)
        self.ui.moneroClip.clicked.connect(self.onMoneroClip)
        self.ui.okButton.clicked.connect(self.close)
        self.ui.bitcoinClip.clicked.connect(self.onBcClip)

        self._moneroAddr = moneroAddr
        self._bcAddr = bcAddr
        self.ui.moneroAddress.setText('<b>{0}</b>'.format(self._moneroAddr))
        self.ui.bitcoinAddress.setText('<b>{0}</b>'.format(self._bcAddr))
        self.setWindowTitle('Make a donation')

    def onMoneroClip(self):
        self.toClip(self._moneroAddr)

    def onBcClip(self):
        self.toClip(self._bcAddr)

    def toClip(self, data):
        app = QCoreApplication.instance()
        app.clipboard().setText(data, QClipboard.Selection)
        app.clipboard().setText(data, QClipboard.Clipboard)

    def close(self):
        self.done(1)

    def accept(self):
        self.done(1)
