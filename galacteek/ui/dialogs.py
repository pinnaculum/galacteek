
import time
import asyncio
import re
import os, os.path

from PyQt5.QtWidgets import (QWidget, QApplication,
        QDialog, QLabel, QTextEdit, QPushButton, QMessageBox)

from PyQt5.QtCore import QUrl, Qt, pyqtSlot, QCoreApplication
from PyQt5.QtGui import QClipboard, QPixmap, QImage

from galacteek import asyncify, ensure, asyncReadFile
from galacteek.core.ipfsmarks import *
from galacteek.core import countries
from galacteek.ipfs import cidhelpers
from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.wrappers import *

from . import ui_addkeydialog, ui_addhashmarkdialog
from . import ui_addfeeddialog
from . import ui_ipfscidinputdialog, ui_ipfsmultiplecidinputdialog
from . import ui_profileeditdialog
from . import ui_donatedialog
from . import ui_profilepostmessage
from .helpers import *

import mimetypes

def boldLabelStyle():
    return 'QLabel { font-weight: bold; }'

class AddHashmarkDialog(QDialog):
    def __init__(self, marks, resource, title, description, stats, parent=None):
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

        if isinstance(description, str):
            self.ui.description.insertPlainText(description)

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
        description = self.ui.description.toPlainText()

        if len(newCat) > 0:
            category = newCat
        else:
            category = self.ui.category.currentText()

        mark = IPFSHashMark.make(self.ipfsResource,
            title=self.ui.title.text(),
            share=share,
            comment=self.ui.comment.text(),
            description=description,
            tags=self.ui.tags.text().split(),
            datasize=self.stats.get('DataSize', None),
            cumulativesize=self.stats.get('CumulativeSize', None),
            numlinks=self.stats.get('NumLinks', None)
        )

        self.marks.insertMark(mark, category)
        self.done(0)

class AddFeedDialog(QDialog):
    def __init__(self, marks, resource, feedName=None, parent=None):
        super().__init__(parent)

        self.marks = marks
        self.ipfsResource = resource

        self.ui = ui_addfeeddialog.Ui_AddFeedDialog()
        self.ui.setupUi(self)
        self.ui.resourceLabel.setText(self.ipfsResource)
        self.ui.resourceLabel.setStyleSheet(boldLabelStyle())

        if isinstance(feedName, str):
            self.ui.feedName.setText(feedName)

    def accept(self):
        share = self.ui.share.isChecked()
        autoPin = self.ui.autoPin.isChecked()

        self.marks.follow(self.ipfsResource, self.ui.feedName.text(),
            resolveevery=self.ui.resolve.value(),
            share=share, autoPin=autoPin)
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
    def __init__(self, bcAddr, parent=None):
        super().__init__(parent)

        self.ui = ui_donatedialog.Ui_DonateDialog()
        self.ui.setupUi(self)
        self.ui.okButton.clicked.connect(self.close)
        self.ui.bitcoinClip.clicked.connect(self.onBcClip)

        self._bcAddr = bcAddr
        self.ui.bitcoinAddress.setText('<b>{0}</b>'.format(self._bcAddr))
        self.setWindowTitle('Make a donation')

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

def notEmpty(v):
    return v != ''

class ProfileEditDialog(QDialog):
    def __init__(self, profile, parent=None):
        super().__init__(parent)

        self.profile = profile
        self.countryList = countries.countryList

        self.ui = ui_profileeditdialog.Ui_ProfileEditDialog()
        self.ui.setupUi(self)

        self.loadCountryData()

        self.ui.labelWarning.setStyleSheet('QLabel { font-weight: bold; }')
        self.ui.username.setText(self.profile.userInfo.username)
        self.ui.firstname.setText(self.profile.userInfo.firstname)
        self.ui.lastname.setText(self.profile.userInfo.lastname)
        self.ui.email.setText(self.profile.userInfo.email)
        self.ui.org.setText(self.profile.userInfo.org)

        if notEmpty(self.profile.userInfo.countryName):
            self.ui.countryBox.setCurrentText(self.profile.userInfo.countryName)
        else:
            self.ui.countryBox.setCurrentText('Unspecified')

        if notEmpty(self.profile.userInfo.avatarCid):
            self.updateAvatarCid()

        self.ui.profileCryptoId.setText('<b>{}</b>'.format(
            self.profile.userInfo.objHash))

        self.ui.changeIconButton.clicked.connect(self.changeIcon)
        self.ui.updateButton.clicked.connect(self.save)
        self.ui.cancelButton.clicked.connect(self.close)

        self.reloadIcon()

    def updateAvatarCid(self):
        self.ui.iconHash.setText('<a href="ipfs:{0}">{1}</a>'.format(
            joinIpfs(self.profile.userInfo.avatarCid),
            self.profile.userInfo.avatarCid))

    def reloadIcon(self):
        ensure(self.loadIcon())

    def getCountryCode(self, name):
        for entry in self.countryList:
            if entry['name'] == name:
                return entry['code']

    def loadCountryData(self):
        for entry in self.countryList:
            self.ui.countryBox.addItem(entry['name'])

        self.ui.countryBox.addItem('Unspecified')

    @asyncify
    async def loadIcon(self):
        @ipfsOpFn
        async def load(op, cid):
            try:
                imgData = await op.client.cat(cid)
                img1 = QImage()
                img1.loadFromData(imgData)
                img = img1.scaledToWidth(256)
                self.ui.iconPixmap.setPixmap(QPixmap.fromImage(img))
            except Exception as e:
                messageBox('Error while loading image')

        if self.profile.userInfo.avatarCid != '':
            await load(self.profile.userInfo.avatarCid)

    def changeIcon(self):
        fps = filesSelect(filter='Images (*.xpm, *.jpg, *.png)')
        if len(fps) > 0:
            ensure(self.setIcon(fps.pop()))

    @ipfsOp
    async def setIcon(self, op, fp):
        entry = await op.addPath(fp, recursive=False)
        if entry:
            self.profile.userInfo.setAvatarCid(entry['Hash'])
            self.reloadIcon()
            self.updateAvatarCid()

    def save(self):
        kw = {}
        for key in ['username', 'firstname',
                    'lastname', 'email', 'org']:
            val = getattr(self.ui, key).text()
            ma = re.search("[a-zA-Z\_\-\@\.\+\'\´0-9\s]*", val)
            if ma:
                kw[key] = val

        country = self.ui.countryBox.currentText()
        code = self.getCountryCode(country)

        if country and code:
            self.profile.userInfo.setCountryInfo(country, code)

        self.profile.userInfo.setInfos(**kw)
        self.done(1)

    def reject(self):
        self.done(0)

class ProfilePostMessageDialog(QDialog):
    def __init__(self, profile, parent=None):
        super().__init__(parent)

        self.profile = profile

        self.ui = ui_profilepostmessage.Ui_PostMessageDialog()
        self.ui.setupUi(self)

    def accept(self):
        ensure(self.post())

    async def post(self):
        msg = self.ui.message.toPlainText()
        title = self.ui.title.text()
        if not title:
            title = 'No title'

        if msg:
            ensure(self.profile.app.postMessage(title, msg))

        self.done(1)
