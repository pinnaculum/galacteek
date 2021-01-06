from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QTreeWidget
from PyQt5.QtWidgets import QTreeWidgetItem
from PyQt5.QtWidgets import QStackedWidget
from PyQt5.QtWidgets import QHeaderView

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QObject
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QModelIndex
from PyQt5.QtCore import QItemSelectionModel

from galacteek import log
from galacteek import partialEnsure
from galacteek import AsyncSignal
from galacteek.core.modelhelpers import *
from galacteek.core import runningApp

from galacteek.ipfs.cidhelpers import IPFSPath

from galacteek.database import bmMailBoxRegister
from galacteek.database import bmMailBoxList
from galacteek.database import bmMailBoxCount
from galacteek.database import bmMailBoxGetDefault
from galacteek.database import bmMailBoxGet
from galacteek.database.models.bm import BitMessageMailBox

from galacteek.services.bitmessage.storage import BitMessageMailDir
from galacteek.services.bitmessage.storage import MaildirMessage
from galacteek.services.bitmessage import bmAddressExtract
from galacteek.services.bitmessage import bmAddressValid

from ..forms import ui_dmessenger
from ..forms import ui_dmessenger_compose
from ..forms import ui_dmessenger_messageview
from ..forms import ui_dmessenger_newmailboxdialog

from ..dialogs import BaseDialog
from ..fonts import QFont
from ..helpers import *
from ..clipboard import iCopiedToClipboard


class CreateMailBoxDialog(BaseDialog):
    uiClass = ui_dmessenger_newmailboxdialog.Ui_NewBitMessageMailBoxDialog

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.ui.buttonBox.accepted.connect(self.accept)
        self.ui.buttonBox.rejected.connect(self.reject)

    def options(self):
        return {
            'label': self.ui.mailBoxLabel.text(),
            'type': self.ui.mailBoxType.currentText()
        }


class MessageViewer(QWidget):
    curMessage: MaildirMessage = None

    msgReplyStart = pyqtSignal(MaildirMessage)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.app = runningApp()

        self.ui = ui_dmessenger_messageview.Ui_MessengerMailView()
        self.ui.setupUi(self)
        self.ui.replyButton.setEnabled(False)
        self.ui.replyButton.clicked.connect(self.onReply)

    @property
    def browser(self):
        return self.ui.textBrowser

    def onReply(self):
        if self.curMessage:
            self.msgReplyStart.emit(self.curMessage)

    def showMessage(self, message: MaildirMessage):
        self.browser.clear()
        self.browser.insertPlainText(str(message))

        self.curMessage = message
        self.ui.replyButton.setEnabled(True)


class MessageComposer(QWidget):
    cancelled = pyqtSignal()
    sendSuccess = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.app = runningApp()
        self.ui = ui_dmessenger_compose.Ui_MessageComposerForm()
        self.ui.setupUi(self)

        self.ui.sendButton.clicked.connect(
            partialEnsure(self.onSend))
        self.ui.cancelButton.clicked.connect(
            partialEnsure(self.onCancelClicked))

    @property
    def messengerWidget(self):
        return self.parent()

    @property
    def subject(self):
        return self.ui.msgSubject.text()

    @property
    def recipient(self):
        return self.ui.msgTo.text()

    @subject.setter
    def subject(self, s: str):
        self.ui.msgSubject.setText(s)

    @recipient.setter
    def recipient(self, s: str):
        self.ui.msgTo.setText(s)

    @property
    def messageBody(self):
        return self.ui.msgText.toPlainText()

    def setSender(self, bmAddress):
        self.ui.msgFrom.clear()
        self.ui.msgFrom.addItem(bmAddress)
        # self.ui.msgFrom.setCurrentText(bmAddress)

    def startReply(self, message: MaildirMessage):
        fromKey = bmAddressExtract(message['From'])

        self.ui.msgTo.setText(fromKey if fromKey else message['From'])

        subject = message.get('Subject', '')
        if not subject.startswith('Re: '):
            self.ui.msgSubject.setText("Re: " + subject)
        else:
            self.ui.msgSubject.setText(subject)

        text = '\n\n'
        text += '-' * 80
        text += '\n'

        try:
            text += message.get_payload()
        except Exception:
            pass

        self.ui.msgText.setPlainText(text)
        self.ui.msgText.setFocus(Qt.OtherFocusReason)

    def composeNew(self):
        self.ui.msgTo.setText('')
        self.subject = ''
        self.recipient = ''
        self.ui.msgText.setPlainText('')
        self.ui.msgTo.setFocus(Qt.OtherFocusReason)

    async def onCancelClicked(self, *qa):
        if self.messageBody:
            if not await areYouSure():
                return

        self.cancelled.emit()

    async def onSend(self, *args):
        if not bmAddressValid(self.recipient):
            return await messageBoxAsync('Invalid recipient BM address')

        # curMailDir = self.messengerWidget.bmCurrentMailDir
        curMailDir = None

        result = await self.app.s.bmService.mailer.send(
            self.ui.msgFrom.currentText(),
            self.ui.msgTo.text(),
            self.ui.msgSubject.text(),
            self.messageBody,
            mailDir=curMailDir
        )

        if result is True:
            self.sendSuccess.emit(self.ui.msgTo.text())
        else:
            await messageBoxAsync('Send error !')


class MessageHandlingError(Exception):
    pass


class MessageListView(QTreeWidget):
    messageNeedsDisplay = pyqtSignal()

    def __init__(self, maildir: BitMessageMailDir, parent=None):
        super().__init__(parent)

        self.maildir = maildir
        self.currentItemChanged.connect(
            partialEnsure(self.onCurMessageChanged))
        self.setColumnCount(2)
        self.setHeaderLabels(['Subject', 'Date'])
        self.setHeaderHidden(True)
        self.setSortingEnabled(True)

        self.sMessageNeedsDisplay = AsyncSignal(MaildirMessage)

        self.fontNoBold = QFont(self.font())
        self.fontNoBold.setBold(False)
        self.fontBold = QFont(self.font())
        self.fontBold.setBold(True)

        self.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.hideColumn(1)

    @property
    def selModel(self):
        return self.selectionModel()

    async def onNewMessageReceived(self, key, msg):
        # TODO: UI notification here

        await self.insertMessage(key, msg)

    async def onCurMessageChanged(self, item, itemPrevious, *a):
        mKey = item.data(0, Qt.UserRole)
        if not mKey:
            return

        msg = await self.maildir.getMessageByKey(mKey)
        await self.sMessageNeedsDisplay.emit(msg)

        for col in range(0, self.columnCount()):
            item.setFont(col, self.fontNoBold)

        # Mark it as read
        msg.set_subdir('cur')
        self.maildir.updateMessage(mKey, msg)

    async def insertMessage(self, mKey, msg):
        idxL = self.model().match(
            self.model().index(0, 0, QModelIndex()),
            Qt.UserRole,
            mKey,
            -1,
            Qt.MatchFixedString | Qt.MatchWrap | Qt.MatchRecursive
        )

        if len(idxL) > 0:
            raise MessageHandlingError(f'Already exists: {mKey}')

        msgSubDir = msg.get_subdir()

        itemFrom = QTreeWidgetItem(self)
        itemFrom.setText(0, msg['Subject'])
        itemFrom.setData(0, Qt.UserRole, mKey)
        itemFrom.setToolTip(0, mKey)
        itemFrom.setText(1, msg['Date'])
        itemFrom.setText(2, msg['From'])

        if msgSubDir == 'new':
            for col in range(0, 3):
                itemFrom.setFont(col, self.fontBold)
        elif msgSubDir == 'cur':
            pass

        self.insertTopLevelItem(0, itemFrom)
        self.sortByColumn(1, Qt.DescendingOrder)

    async def refresh(self):
        async for mKey, msg in self.maildir.yieldNewMessages():
            try:
                await self.insertMessage(mKey, msg)
            except Exception as err:
                log.debug(f'Refresh error: {err}')
                continue

        # Select latest message
        curIndex = self.selModel.currentIndex()
        if not curIndex.isValid():
            idxLatest = self.model().index(0, 0, QModelIndex())
            if idxLatest.isValid():
                self.selModel.select(
                    idxLatest, QItemSelectionModel.Select)
                self.selModel.setCurrentIndex(
                    idxLatest, QItemSelectionModel.SelectCurrent)


class Messenger(QObject):
    bmCurrentMailDir: BitMessageMailDir = None
    messageBoxViews: []
    mBoxStack: QStackedWidget = None

    def __init__(self, mBoxStack, parent=None):
        super().__init__(parent)

        self.mBoxStack = mBoxStack


class MessengerWidget(QWidget):
    bmCurrentMailDir: BitMessageMailDir = None
    bmCurrentMailBox: BitMessageMailBox = None
    currentView: MessageListView = None
    messageBoxViews: dict = {}

    def __init__(self, parent=None):
        super().__init__(parent)

        self.app = runningApp()
        self.ui = ui_dmessenger.Ui_MessengerForm()
        self.ui.setupUi(self)

        self.messenger = Messenger(self.ui.mailBoxStack, self)

        self.messageView = MessageViewer(self)
        self.messageView.msgReplyStart.connect(
            self.onReplyToMessage
        )

        self.messageComposer = MessageComposer(self)
        self.messageComposer.cancelled.connect(
            self.setDefaultView)
        self.messageComposer.sendSuccess.connect(
            self.onSendSuccess)

        self.sIdxView = self.ui.mailStack.addWidget(self.messageView)
        self.sIdxCompose = self.ui.mailStack.addWidget(self.messageComposer)

        self.ui.createMailboxButton.clicked.connect(
            partialEnsure(self.onCreateMailbox))
        self.ui.copyBmKeyButton.clicked.connect(
            partialEnsure(self.onCopyBmKey))
        self.ui.composeButton.clicked.connect(
            self.onCompose)
        self.ui.curMailboxCombo.currentIndexChanged.connect(
            partialEnsure(self.onMailBoxSelect))

        self.setDefaultView()

    @property
    def bmComboText(self):
        return self.ui.curMailboxCombo.currentText()

    @property
    def bmComboItems(self):
        return [
            self.ui.curMailboxCombo.itemText(idx) for idx in
            range(self.ui.curMailboxCombo.count())
        ]

    @property
    def isComposing(self):
        return self.ui.mailStack.currentIndex() == self.sIdxCompose

    def resizeEventNo(self, event):
        try:
            for _addr, view in self.messageBoxViews.items():
                view.setMaximumWidth(self.width() / 3)
        except Exception:
            pass

    def setDefaultView(self):
        self.ui.mailStack.setCurrentIndex(self.sIdxView)

    def setComposeView(self):
        self.ui.mailStack.setCurrentIndex(self.sIdxCompose)

    async def updateMailBoxList(self):
        defaultIcon = getIcon('dmessenger/dmessenger.png')

        for bmBox in await bmMailBoxList():
            if bmBox.bmAddress not in self.bmComboItems:
                if bmBox.iconCid:
                    icon = await getIconFromIpfs(IPFSPath(bmBox.iconCid))

                    self.ui.curMailboxCombo.addItem(
                        icon if icon else defaultIcon,
                        bmBox.bmAddress
                    )
                else:
                    self.ui.curMailboxCombo.addItem(
                        defaultIcon,
                        bmBox.bmAddress
                    )

    async def setup(self):
        if await bmMailBoxCount() == 0:
            bmMb, bmKey, mailDir = await self.createMailBox(
                label='me', select=False,
                default=True)

        await self.updateMailBoxList()

        bmMbDefault = await bmMailBoxGetDefault()

        if bmMbDefault:
            self.bmCurrentMailBox = bmMbDefault

            await self.selectMailBox(bmMbDefault.bmAddress)

    async def onMessageDisplay(self, message):
        self.messageView.showMessage(message)

        if not self.isComposing and 0:
            self.setDefaultView()

    async def onMailBoxSelect(self, idx, *qa):
        await self.selectMailBox(self.bmComboText)

    def onReplyToMessage(self, message):
        self.messageComposer.setSender(
            self.bmCurrentMailBox.bmAddress
        )
        self.messageComposer.startReply(message)
        self.setComposeView()

    def onSendSuccess(self, recipient):
        self.setDefaultView()

    def onCompose(self):
        if self.bmCurrentMailBox:
            self.messageComposer.composeNew()
            self.messageComposer.setSender(
                self.bmCurrentMailBox.bmAddress
            )

            self.setComposeView()

    async def switchMailDir(self, bmAddr, maildir: BitMessageMailDir):
        view = self.messageBoxViews.get(bmAddr)

        if not view:
            view = MessageListView(maildir, parent=self.ui.mailBoxStack)
            self.messageBoxViews[bmAddr] = view
            idx = self.ui.mailBoxStack.addWidget(view)
            self.ui.mailBoxStack.setCurrentIndex(idx)

            view.sMessageNeedsDisplay.connectTo(
                self.onMessageDisplay)
            maildir.sNewMessage.connectTo(
                view.onNewMessageReceived)
        else:
            self.ui.mailBoxStack.setCurrentWidget(view)

        self.currentView = view
        await view.refresh()

    async def onCopyBmKey(self, *args):
        if self.bmComboText:
            self.app.setClipboardText(self.bmComboText)
            await messageBoxAsync(iCopiedToClipboard())

    async def onCreateMailbox(self, *args):
        dlg = CreateMailBoxDialog()
        await runDialogAsync(dlg)
        opts = dlg.options()

        await self.createMailBox(
            label=opts['label'],
            select=True
        )

        await self.updateMailBoxList()

    async def selectMailBox(self, bmAddress: str):
        # self.ui.curMailboxCombo.setCurrentText(bmAddress)
        mailBox = await bmMailBoxGet(bmAddress)

        if mailBox:
            self.ui.curMailboxCombo.setCurrentText(bmAddress)

            key, mailDir = await self.app.s.bmService.mailer.getMailBox(
                bmAddress)
            self.bmCurrentMailDir = mailDir
            self.bmCurrentMailBox = mailBox

            await self.switchMailDir(bmAddress, mailDir)

    async def createMailBox(self, label='default', select=False,
                            default=False):
        key, mailDir = await self.app.s.bmService.mailer.createMailBox()
        if not key:
            return None, None, None

        await mailDir.storeWelcome()

        if select:
            await self.selectMailBox(key)

        bmMailBox = await bmMailBoxRegister(key, label, key, default=default)
        return key, bmMailBox, mailDir
