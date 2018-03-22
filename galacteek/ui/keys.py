
import sys
import time
import os.path

from PyQt5.QtWidgets import (QWidget, QFrame, QApplication, QMainWindow,
        QDialog, QLabel, QTextEdit, QPushButton, QVBoxLayout, QAction)
from PyQt5.QtWidgets import (QTreeView)
from PyQt5.QtWidgets import QMessageBox

from PyQt5.QtGui import QStandardItemModel, QStandardItem

from PyQt5.QtCore import QUrl, Qt, pyqtSlot

from . import ui_keys, ui_addkeydialog
from .modelhelpers import *

class AddKeyDialog(QDialog):
    def __init__(self, app, parent=None):
        super().__init__(parent)

        self.app = app
        self.ui = ui_addkeydialog.Ui_AddKeyDialog()
        self.ui.setupUi(self)

    def accept(self):
        keyName = self.ui.keyName.text()
        keySizeText = self.ui.keySize.currentText()

        async def createKey(client):
            reply = await client.key.gen(keyName, type='rsa',
                size=int(keySizeText))
            self.done(0)

        self.app.ipfsTask(createKey)

    def reject(self):
        self.done(0)

class KeysView(QTreeView):
    def mousePressEvent (self, event):
        if event.button() == Qt.RightButton:
            pass
        QTreeView.mousePressEvent(self, event)

class KeysTab(QWidget):
    def __init__(self, mainWindow, parent = None):
        super(QWidget, self).__init__(parent = parent)

        self.mainWindow = mainWindow
        self.app = self.mainWindow.getApp()

        self.ui = ui_keys.Ui_KeysForm()
        self.ui.setupUi(self)

        self.ui.addKeyButton.clicked.connect(self.onAddKeyClicked)

        self.model = QStandardItemModel(parent=self)

        self.ui.treeKeys = KeysView()
        self.ui.treeKeys.doubleClicked.connect(self.onItemDoubleClicked)
        self.ui.treeKeys.setModel(self.model)
        self.ui.verticalLayout.addWidget(self.ui.treeKeys)

        self.updateKeysList()

    def setupModel(self):
        self.model.clear()
        self.model.setColumnCount(2)
        self.model.setHorizontalHeaderLabels(['Name', 'Hash'])

    def onAddKeyClicked(self):
        dlg = AddKeyDialog(self.app)
        dlg.exec_()
        dlg.show()

    def updateKeysList(self):
        self.setupModel()
        async def listKeys(client):
            keys = await client.key.list(long=True)
            for key in keys['Keys']:
                found = modelSearch(self.model, search=key['Name'])
                if len(found) > 0:
                    continue
                item1 = QStandardItem(key['Name'])
                item2 = QStandardItem(key['Id'])
                self.model.appendRow([item1, item2])

        self.app.ipfsTask(listKeys)

    def onItemDoubleClicked(self, index):
        row = index.row()
        keyHash = self.model.data(self.model.index(row, 1))
        tab = self.mainWindow.addBrowserTab()
        tab.browseIpnsHash(keyHash)
