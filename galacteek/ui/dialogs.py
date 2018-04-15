
import time

from PyQt5.QtWidgets import (QWidget, QApplication,
        QDialog, QLabel, QTextEdit, QPushButton, QMessageBox)

from PyQt5.QtCore import QUrl, Qt, pyqtSlot

from galacteek.core.ipfsmarks import *
from galacteek.ipfs import cidhelpers

from . import ui_addkeydialog, ui_addbookmarkdialog
from . import ui_addfeeddialog
from . import ui_ipfscidinputdialog, ui_ipfsmultiplecidinputdialog

import mimetypes

def boldLabelStyle():
    return 'QLabel { font-weight: bold; }'

class AddBookmarkDialog(QDialog):
    def __init__(self, marks, resource, title, stats, parent=None):
        super().__init__(parent)

        self.ipfsResource = resource
        self.marks = marks
        self.stats = stats # ipfs object stat

        self.ui = ui_addbookmarkdialog.Ui_AddBookmarkDialog()
        self.ui.setupUi(self)
        self.ui.resourceLabel.setText(self.ipfsResource)
        self.ui.resourceLabel.setStyleSheet(boldLabelStyle())
        self.ui.title.setText(title)

        for cat in self.marks.getCategories():
            self.ui.category.addItem(cat)

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
            tags=self.ui.tags.text().split(' '),
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

    def onCIDChanged(self, text):
        if cidhelpers.cidValid(text):
            self.ui.validity.setText('Valid CID')
            self.validCid = True
        else:
            self.ui.validity.setText('Invalid CID')
            self.validCid = False

    def getHash(self):
        cid = self.getCID()
        if cid:
            return str(cid)

    def getCID(self):
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
