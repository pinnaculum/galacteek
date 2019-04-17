from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QTreeView
from PyQt5.QtWidgets import QHeaderView
from PyQt5.QtWidgets import QWidget

from PyQt5.QtGui import QStandardItemModel
from PyQt5.QtCore import Qt, QCoreApplication

from galacteek.ipfs.wrappers import ipfsOp

from . import ui_keys, ui_addkeydialog
from .modelhelpers import *
from .widgets import GalacteekTab
from .helpers import *

from .i18n import iUnknown
from .i18n import iMultihash


def iKeyName():
    return QCoreApplication.translate('KeysForm', 'Name')


def iKeyResolve():
    return QCoreApplication.translate('KeysForm', 'Resolves to')


class AddKeyDialog(QDialog):
    def __init__(self, app, parent=None):
        super().__init__(parent)

        self.keysView = parent

        self.app = app
        self.ui = ui_addkeydialog.Ui_AddKeyDialog()
        self.ui.setupUi(self)

    def accept(self):
        keyName = self.ui.keyName.text()
        keySizeText = self.ui.keySize.currentText()

        self.app.task(self.createKey, keyName, int(keySizeText))

    @ipfsOp
    async def createKey(self, ipfsop, keyName, keySize):
        await ipfsop.client.key.gen(keyName,
                                    type='rsa', size=keySize)
        self.done(1)
        self.keysView.updateKeysList()

    def reject(self):
        self.done(0)


class KeysView(QTreeView):
    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            pass
        QTreeView.mousePressEvent(self, event)


class KeysTab(GalacteekTab):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

        self.keysW = QWidget()
        self.addToLayout(self.keysW)
        self.ui = ui_keys.Ui_KeysForm()
        self.ui.setupUi(self.keysW)

        self.ui.addKeyButton.clicked.connect(self.onAddKeyClicked)
        self.ui.deleteKeyButton.clicked.connect(self.onDelKeyClicked)

        self.model = QStandardItemModel(parent=self)

        self.ui.treeKeys = KeysView()
        self.ui.treeKeys.doubleClicked.connect(self.onItemDoubleClicked)
        self.ui.treeKeys.setModel(self.model)

        self.ui.verticalLayout.addWidget(self.ui.treeKeys)

        self.setupModel()
        self.app.task(self.listKeys)

    def setupModel(self):
        self.model.clear()
        self.model.setColumnCount(3)
        self.model.setHorizontalHeaderLabels([
            iKeyName(), iMultihash(), iKeyResolve()])
        self.ui.treeKeys.header().setSectionResizeMode(
            0, QHeaderView.ResizeToContents)
        self.ui.treeKeys.header().setSectionResizeMode(
            1, QHeaderView.ResizeToContents)

    def onDelKeyClicked(self):
        idx = self.ui.treeKeys.currentIndex()
        idxName = self.model.index(idx.row(), 0, idx.parent())
        keyName = self.model.data(idxName)
        if keyName:
            self.app.task(self.delKey, keyName)

    def onAddKeyClicked(self):
        runDialog(AddKeyDialog, self.app, parent=self)

    @ipfsOp
    async def delKey(self, ipfsop, name):
        if await ipfsop.keysRemove(name):
            modelDelete(self.model, name)
        self.updateKeysList()

    @ipfsOp
    async def listKeys(self, ipfsop):
        keys = await ipfsop.keys()
        for key in keys:
            found = modelSearch(self.model, search=key['Name'])
            if len(found) > 0:
                continue
            resolveItem = UneditableItem('')
            self.model.appendRow([
                UneditableItem(key['Name']),
                UneditableItem(key['Id']),
                resolveItem
            ])
            self.app.task(self.keyResolve, key, resolveItem)

    @ipfsOp
    async def keyResolve(self, ipfsop, key, item):
        resolved = await ipfsop.resolve(key['Id'])
        if resolved:
            item.setText(resolved['Path'])
        else:
            item.setText(iUnknown())

    def updateKeysList(self):
        self.app.task(self.listKeys)

    def onItemDoubleClicked(self, index):
        # Browse IPNS key associated with current item on double-click
        keyHash = self.model.data(self.model.index(index.row(), 1))
        self.gWindow.addBrowserTab().browseIpnsHash(keyHash)
