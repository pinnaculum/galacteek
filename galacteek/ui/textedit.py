
from PyQt5.QtWidgets import QWidget, QTextEdit, QAction
from PyQt5.QtWidgets import QMessageBox

from PyQt5.QtCore import QUrl, Qt, QTemporaryFile, QTemporaryDir, QSaveFile
from PyQt5.QtCore import QIODevice

from . import ui_newdocument
from .helpers import *
from galacteek.ipfs.ipfsops import *

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
            return messageBox('Please specify a filename')

        text = self.ui.textEdit.toPlainText()
        tempDir = QTemporaryDir()

        if not tempDir.isValid():
            return messageBox('Error creating directory')

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
        messageBox('Succesfully imported {0} (hash {1})'.format(filename,
            entry))
        self.gWindow.removeTabFromWidget(self)

    def onImport(self):
        self.app.ipfsTaskOp(self.importFile)
