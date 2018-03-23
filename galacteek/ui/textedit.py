
from PyQt5.QtWidgets import QWidget, QTextEdit, QAction
from PyQt5.QtWidgets import QMessageBox

from PyQt5.QtCore import QUrl, Qt, QTemporaryFile, QTemporaryDir, QSaveFile
from PyQt5.QtCore import QIODevice

from . import ui_newdocument
from .helpers import *
from .i18n import *
from galacteek.ipfs.ipfsops import *

def iImportedDocument(name, hash):
    return QCoreApplication.translate('NewDocumentForm',
        'Succesfully imported {0} (hash reference {1})').format(name, hash)

class AddDocumentWidget(QWidget):
    def __init__(self, gWindow, parent = None):
        super(QWidget, self).__init__(parent = parent)

        self.gWindow = gWindow
        self.app = self.gWindow.getApp()
        self.ui = ui_newdocument.Ui_NewDocumentForm()
        self.ui.setupUi(self)

        self.ui.importButton.clicked.connect(self.onImport)

    async def importFile(self, op):
        filename = self.ui.filename.text()
        if filename == '':
            return messageBox(iGeneralError('Please specify a filename'))

        text = self.ui.textEdit.toPlainText()
        tempDir = QTemporaryDir()

        if not tempDir.isValid():
            return messageBox(iGeneralError('Error creating directory'))

        tempFilePath = tempDir.filePath(filename)

        tempFile = QSaveFile(tempFilePath)
        tempFile.open(QIODevice.WriteOnly)
        tempFile.write(text.encode('utf-8'))
        tempFile.commit()

        root = None
        async for added in op.client.core.add(tempFile.fileName(),
                wrap_with_directory=True):
            if added['Name'] == '':
                root = added
                await op.filesLink(added, GFILES_MYFILES_PATH,
                    name=filename)

        self.success(filename, root)

    def success(self, filename, entry):
        messageBox(iImportedDocument(filename, entry['Hash']))
        self.gWindow.removeTabFromWidget(self)

    def onImport(self):
        self.app.ipfsTaskOp(self.importFile)
