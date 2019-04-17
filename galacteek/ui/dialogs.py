import re

from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QInputDialog

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import QRegExp
from PyQt5.QtCore import Qt

from PyQt5.QtGui import QClipboard
from PyQt5.QtGui import QPixmap
from PyQt5.QtGui import QImage
from PyQt5.QtGui import QRegExpValidator

from galacteek import asyncify, ensure
from galacteek.core.ipfsmarks import *
from galacteek.core import countries
from galacteek.core.profile import UserInfos
from galacteek.ipfs import cidhelpers
from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.wrappers import ipfsOp, ipfsOpFn

from . import ui_addhashmarkdialog
from . import ui_addfeeddialog
from . import ui_ipfscidinputdialog, ui_ipfsmultiplecidinputdialog
from . import ui_profileeditdialog
from . import ui_donatedialog
from . import ui_profilepostmessage
from .helpers import *
from .widgets import ImageWidget

from .i18n import iDoNotPin
from .i18n import iPinSingle
from .i18n import iPinRecursive
from .i18n import iNoTitleProvided


def boldLabelStyle():
    return 'QLabel { font-weight: bold; }'


class AddHashmarkDialog(QDialog):
    def __init__(
            self,
            marks,
            resource,
            title,
            description,
            stats,
            pin=False,
            pinRecursive=False,
            parent=None):
        super().__init__(parent)

        self.ipfsResource = resource
        self.marks = marks
        self.stats = stats if stats else {}
        self.iconCid = None

        self.ui = ui_addhashmarkdialog.Ui_AddHashmarkDialog()
        self.ui.setupUi(self)
        self.ui.resourceLabel.setText(self.ipfsResource)
        self.ui.resourceLabel.setStyleSheet(boldLabelStyle())
        self.ui.newCategory.textChanged.connect(self.onNewCatChanged)
        self.ui.selectIconButton.clicked.connect(self.onSelectIcon)
        self.ui.title.setText(title)
        self.iconWidget = ImageWidget()
        self.ui.layoutIcon.addWidget(self.iconWidget, 0, Qt.AlignCenter)

        self.ui.pinCombo.addItem(iDoNotPin())
        self.ui.pinCombo.addItem(iPinSingle())
        self.ui.pinCombo.addItem(iPinRecursive())

        regexp1 = QRegExp("[A-Za-z\/\_]+")  # noqa
        self.ui.newCategory.setValidator(QRegExpValidator(regexp1))

        if pin is True:
            self.ui.pinCombo.setCurrentIndex(1)
        elif pinRecursive is True:
            self.ui.pinCombo.setCurrentIndex(2)

        if isinstance(description, str):
            self.ui.description.insertPlainText(description)

        for cat in self.marks.getCategories():
            self.ui.category.addItem(cat)

    def onSelectIcon(self):
        fps = filesSelectImages()
        if len(fps) > 0:
            ensure(self.setIcon(fps.pop()))

    @ipfsOp
    async def setIcon(self, op, fp):
        entry = await op.addPath(fp, recursive=False)
        if entry:
            cid = entry['Hash']

            if await self.iconWidget.load(cid):
                self.iconCid = cid

    def onNewCatChanged(self, text):
        self.ui.category.setEnabled(len(text) == 0)

    def accept(self):
        title = self.ui.title.text()

        if len(title) == 0:
            return messageBox(iNoTitleProvided())

        share = self.ui.share.isChecked()
        newCat = self.ui.newCategory.text()
        description = self.ui.description.toPlainText()

        if len(newCat) > 0:
            category = re.sub('//', '', newCat)
        else:
            category = self.ui.category.currentText()

        pSingle = (self.ui.pinCombo.currentIndex() == 1)
        pRecursive = (self.ui.pinCombo.currentIndex() == 2)

        mark = IPFSHashMark.make(
            self.ipfsResource,
            title=title,
            share=share,
            comment=self.ui.comment.text(),
            description=description,
            tags=self.ui.tags.text().split(),
            pinSingle=pSingle,
            pinRecursive=pRecursive,
            icon=self.iconCid,
            datasize=self.stats.get(
                'DataSize',
                None),
            cumulativesize=self.stats.get(
                'CumulativeSize',
                None),
            numlinks=self.stats.get(
                'NumLinks',
                None))

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
        except BaseException:
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
    genderMapping = {
        'Unspecified': UserInfos.GENDER_UNSPECIFIED,
        'Male': UserInfos.GENDER_MALE,
        'Female': UserInfos.GENDER_FEMALE
    }

    def __init__(self, profile, parent=None):
        super().__init__(parent)

        self.profile = profile
        self.countryList = countries.countryList
        self.previousUsername = self.profile.userInfo.username

        self.ui = ui_profileeditdialog.Ui_ProfileEditDialog()
        self.ui.setupUi(self)
        self.ui.tabWidget.setCurrentIndex(0)

        self.loadCountryData()

        self.ui.labelWarning.setStyleSheet('QLabel { font-weight: bold; }')
        self.ui.username.setText(self.profile.userInfo.username)
        self.ui.firstname.setText(self.profile.userInfo.firstname)
        self.ui.lastname.setText(self.profile.userInfo.lastname)
        self.ui.email.setText(self.profile.userInfo.email)
        self.ui.org.setText(self.profile.userInfo.org)
        self.ui.city.setText(self.profile.userInfo.city)
        self.ui.bio.setText(self.profile.userInfo.bio)

        for gender, gvalue in self.genderMapping.items():
            self.ui.gender.addItem(gender)
            if self.profile.userInfo.gender == gvalue:
                self.ui.gender.setCurrentText(gender)

        if notEmpty(self.profile.userInfo.countryName):
            self.ui.countryBox.setCurrentText(
                self.profile.userInfo.countryName)
        else:
            self.ui.countryBox.setCurrentText('Unspecified')

        if notEmpty(self.profile.userInfo.avatarCid):
            self.updateAvatarCid()

        self.ui.profileCryptoId.setText('<b>{0}</b>'.format(
            self.profile.userInfo.objHash))

        self.ui.changeIconButton.clicked.connect(self.changeIcon)
        self.ui.updateButton.clicked.connect(self.save)
        self.ui.cancelButton.clicked.connect(self.close)

        self.reloadIcon()

    def updateAvatarCid(self):
        self.ui.iconHash.setText('<a href="ipfs:{0}">{1}</a>'.format(
            cidhelpers.joinIpfs(self.profile.userInfo.avatarCid),
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
            except Exception:
                messageBox('Error while loading image')

        if self.profile.userInfo.avatarCid != '':
            await load(self.profile.userInfo.avatarCid)

    def changeIcon(self):
        fps = filesSelectImages()
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
                    'lastname', 'email', 'org',
                    'city']:
            val = getattr(self.ui, key).text()
            ma = re.search(r"[a-zA-Z\_\-\@\.\+\'\´0-9\s]*", val)
            if ma:
                kw[key] = val

        try:
            kw['bio'] = self.ui.bio.toPlainText()
        except:
            pass

        country = self.ui.countryBox.currentText()
        code = self.getCountryCode(country)

        if country and code:
            self.profile.userInfo.setCountryInfo(country, code)

        genderSelected = self.ui.gender.currentText()
        for gender, gvalue in self.genderMapping.items():
            if genderSelected == gender:
                kw['gender'] = gvalue

        self.profile.userInfo.setInfos(**kw)

        if self.previousUsername != self.profile.userInfo.username:
            self.profile.userInfo.usernameChanged.emit()

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


class ChooseProgramDialog(QInputDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle('Choose a program')
        self.setInputMode(QInputDialog.TextInput)
        self.setLabelText(
            '''Command arguments (example: <b>mupdf %f</b>).
                <b>%f</b> is replaced with the file path''')
