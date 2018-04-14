
from PyQt5.QtWidgets import QDialog, QPushButton, QVBoxLayout, QAction
from PyQt5.QtWidgets import QTreeView

from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt

from . import ui_keys, ui_addkeydialog
from .modelhelpers import *
from .widgets import GalacteekTab
from .i18n import *

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

        async def createKey(client):
            reply = await client.key.gen(keyName,
                type='rsa', size=int(keySizeText))
            self.done(0)
            self.keysView.updateKeysList()

        self.app.ipfsTask(createKey)

    def reject(self):
        self.done(0)

class KeysView(QTreeView):
    def mousePressEvent (self, event):
        if event.button() == Qt.RightButton:
            pass
        QTreeView.mousePressEvent(self, event)

class KeysTab(GalacteekTab):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

        self.ui = ui_keys.Ui_KeysForm()
        self.ui.setupUi(self)

        self.ui.addKeyButton.clicked.connect(self.onAddKeyClicked)
        self.ui.deleteKeyButton.clicked.connect(self.onDelKeyClicked)

        self.model = QStandardItemModel(parent=self)

        self.ui.treeKeys = KeysView()
        self.ui.treeKeys.doubleClicked.connect(self.onItemDoubleClicked)
        self.ui.treeKeys.setModel(self.model)
        self.ui.verticalLayout.addWidget(self.ui.treeKeys)

        self.setupModel()
        self.updateKeysList()

    def setupModel(self):
        self.model.clear()
        self.model.setColumnCount(2)
        self.model.setHorizontalHeaderLabels([
            iFileName(), iFileHash()])

    def onDelKeyClicked(self):
        async def delKey(op, name):
            if await op.keysRemove(name):
                modelDelete(self.model, name)
            self.updateKeysList()

        idx = self.ui.treeKeys.currentIndex()
        idxName = self.model.index(idx.row(), 0, idx.parent())
        keyName = self.model.data(idxName)
        if keyName:
            self.app.ipfsTaskOp(delKey, keyName)

    def onAddKeyClicked(self):
        dlg = AddKeyDialog(self.app, parent=self)
        dlg.exec_()
        dlg.show()

    def updateKeysList(self):
        async def listKeys(client):
            keys = await client.key.list(long=True)
            for key in keys['Keys']:
                found = modelSearch(self.model, search=key['Name'])
                if len(found) > 0:
                    continue
                self.model.appendRow([
                    UneditableItem(key['Name']),
                    UneditableItem(key['Id'])
                ])

        self.app.ipfsTask(listKeys)

    def onItemDoubleClicked(self, index):
        # Browse IPNS key associated with current item on double-click
        keyHash = self.model.data(self.model.index(index.row(), 1))
        self.gWindow.addBrowserTab().browseIpnsHash(keyHash)
