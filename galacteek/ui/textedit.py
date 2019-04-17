from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import QTemporaryDir, QSaveFile
from PyQt5.QtCore import QIODevice, pyqtSignal

from . import ui_newdocument
from .helpers import *
from .widgets import *
from .i18n import *
from galacteek.ipfs.ipfsops import *
from galacteek.appsettings import *
from galacteek.ipfs.wrappers import ipfsOp


def iImportedDocument(name, hash):
    return QCoreApplication.translate(
        'NewDocumentForm',
        'Succesfully imported {0} in the Documents folder '
        '(hash reference {1})').format(
        name, hash)


def iImportError():
    return QCoreApplication.translate('NewDocumentForm',
                                      'File import error')


class AddDocumentWidget(GalacteekTab):
    importSuccess = pyqtSignal(str, dict)

    def __init__(self, gWindow, *args, **kw):
        super(AddDocumentWidget, self).__init__(gWindow, *args, **kw)

        self.docWidget = QWidget()
        self.addToLayout(self.docWidget)

        self.ui = ui_newdocument.Ui_NewDocumentForm()
        self.ui.setupUi(self.docWidget)
        self.ui.importButton.clicked.connect(self.onImport)
        self.importSuccess.connect(self.onSuccess)

    @ipfsOp
    async def importFile(self, op):
        wrapEnabled = self.app.settingsMgr.isTrue(
            CFG_SECTION_UI, CFG_KEY_WRAPSINGLEFILES)
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

        root = await op.addPath(tempFile.fileName(), wrap=wrapEnabled)
        if await op.filesLink(root, self.profile.pathDocuments, name=filename):
            self.importSuccess.emit(filename, root)
        else:
            messageBox(iImportError())

    def onSuccess(self, filename, entry):
        messageBox(iImportedDocument(filename, entry['Hash']))
        self.gWindow.removeTabFromWidget(self)

    def onImport(self):
        self.app.task(self.importFile)
