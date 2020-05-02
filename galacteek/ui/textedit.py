import functools
import aiofiles
import os.path
import os
import uuid
import re
import shutil
from pathlib import Path
from datetime import datetime

from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QCheckBox
from PyQt5.QtWidgets import QScrollArea
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QTextEdit
from PyQt5.QtWidgets import QPlainTextEdit
from PyQt5.QtWidgets import QPlainTextDocumentLayout
from PyQt5.QtWidgets import QSpacerItem
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QToolButton
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QFileSystemModel
from PyQt5.QtWidgets import QTreeView
from PyQt5.QtWidgets import QMenu

from PyQt5.QtCore import QFileInfo
from PyQt5.QtCore import QDateTime
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QRegularExpression
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QDir
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import QModelIndex
from PyQt5.QtCore import QItemSelectionModel

from PyQt5.QtGui import QMouseEvent
from PyQt5.QtGui import QTextDocument
from PyQt5.QtGui import QTextFormat
from PyQt5.QtGui import QTextCursor
from PyQt5.QtGui import QColor
from PyQt5.QtGui import QSyntaxHighlighter
from PyQt5.QtGui import QTextCharFormat
from PyQt5.QtGui import QFont

from galacteek import log
from galacteek.ipfs.ipfsops import *
from galacteek.core import isoformat
from galacteek.core.asynclib import asyncReadTextFileChunked
from galacteek.appsettings import *
from galacteek.ipfs import ipfsOp
from galacteek.ipfs import megabytes
from galacteek.ipfs.stat import StatInfo
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ipfs.mimetype import detectMimeTypeFromFile
from galacteek.dweb.markdown import markitdown

from .helpers import *

from .widgets import AnimatedLabel
from .widgets import IPFSPathClipboardButton
from .widgets import IPFSUrlLabel
from .widgets import GalacteekTab
from .widgets import CheckableToolButton
from .clips import RotatingCubeRedFlash140d
from .i18n import *


def iSave():
    return QCoreApplication.translate('textEditor',
                                      'Save')


def iEdit():
    return QCoreApplication.translate('textEditor',
                                      'Edit')


def iMarkdownPreview():
    return QCoreApplication.translate('textEditor',
                                      'Markdown preview')


class PythonSyntaxHighlighter(QSyntaxHighlighter):
    """
    An horrendous Python syntax highligher
    """

    def __init__(self, doc):
        super().__init__(doc)

        self.fmt1 = self.charFormat(color=Qt.red)
        self.fmt2 = self.charFormat(color=Qt.blue)
        self.fmt3 = self.charFormat(color=QColor('#AA1811'))
        self.fmt4 = self.charFormat(color=QColor('#6C0404'))
        self.fmt5 = self.charFormat(color=QColor('#65416C'))

        self.exprs = [
            (r'^(?<instr>from)\s', self.fmt1),
            (r'\s*(?<instr>import)\s', self.fmt1),
            (r'(?<instr>def) ', self.fmt3),
            (r'(?<instr>\s*(async|await|print|return|yield|pass|raise)) ',
                self.fmt3),
            (r'(?<instr>\s*(True|False|None))\s', self.fmt5),
            (r'^(?<instr>class)\s', self.fmt4),
            (r"(?<instr>('[a-zA-Z0-9_-]*'))", self.fmt4),
            (r"(?<instr>(\"[a-zA-Z0-9_-]*\"))", self.fmt4),
            (r"^((?<instr>(\s+)(if|elif|else|or|not|is)\s)", self.fmt4),
            (r"^((?<instr>(\s+)(try|except))\s", self.fmt4),
            (r"^(?<instr>(\s*)#.*$)", self.fmt5),
        ]

    def charFormat(self, color=Qt.red, fontWeight=QFont.Bold):
        fmt = QTextCharFormat()
        fmt.setFontWeight(fontWeight)
        fmt.setForeground(color)
        return fmt

    def highlightBlock(self, text):
        for expr in self.exprs:
            fmt = expr[1]
            rExpr = QRegularExpression(expr[0])

            if not rExpr.isValid():
                continue

            matches = rExpr.globalMatch(text)

            if not matches.isValid():
                continue

            while matches.hasNext():
                match = matches.next()
                instr = match.captured('instr')
                if instr:
                    self.setFormat(
                        match.capturedStart(), match.capturedLength(), fmt)


defaultStyleSheet = '''
    QPlainTextEdit {
        padding: 5px;
        color: #242424;
        background-color: #F0F7F7;
        font: 14pt "Courier";
    }
'''


class EditorLegacy(QTextEdit):
    def __init__(self, parent, lineWrap=80, tabReplace=False):
        super(Editor, self).__init__(parent)

        self.setLineWrapMode(QTextEdit.FixedColumnWidth)
        self.setLineWrapColumnOrWidth(lineWrap)
        self.setStyleSheet(defaultStyleSheet)
        self.tabReplace = tabReplace

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Tab and self.tabReplace:
            self.insertPlainText(' ' * 4)
        else:
            super().keyPressEvent(event)

    def connectSignals(self):
        disconnectSig(self.cursorPositionChanged, self.highlightCurrentLine)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)

    def highlightCurrentLine(self):
        extraSelections = []

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            lineColor = QColor('#e2dd8e')

            selection.format.setBackground(lineColor)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)

        self.setExtraSelections(extraSelections)


class Editor(QPlainTextEdit):
    def __init__(self, parent, lineWrap=80, tabReplace=False):
        super(Editor, self).__init__(parent)

        self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.setStyleSheet(defaultStyleSheet)
        self.tabReplace = tabReplace

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Tab and self.tabReplace:
            self.insertPlainText(' ' * 4)
        else:
            super().keyPressEvent(event)

    def connectSignals(self):
        disconnectSig(self.cursorPositionChanged, self.highlightCurrentLine)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)

    def highlightCurrentLine(self):
        extraSelections = []

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            lineColor = QColor('#e2dd8e')

            selection.format.setBackground(lineColor)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)

        self.setExtraSelections(extraSelections)


class EditHistory(QScrollArea):
    def __init__(self, widgetHeight=60, parent=None):
        super(EditHistory, self).__init__(parent)

        self.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.setWidgetResizable(True)
        self.setMaximumHeight(widgetHeight)

        self.frame = QFrame(self)
        self.frame.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.fLayout = QVBoxLayout()
        self.frame.setLayout(self.fLayout)
        self.setWidget(self.frame)


class Document(QTextDocument):
    modified = pyqtSignal()
    filenameChanged = pyqtSignal(str)

    def __init__(self, encoding=None, name=None, text='', parent=None,
                 textLayout=True):
        super().__init__(text, parent)

        if textLayout is True:
            self.setDocumentLayout(QPlainTextDocumentLayout(self))

        self._filename = name
        self._changed = False
        self._encoding = encoding if encoding else 'utf-8'
        self._previewDocument = None
        self.setDefaultStyleSheet(defaultStyleSheet)
        self.setModified(False)
        self.modificationChanged.connect(self.onModifChange)

    @property
    def previewDocument(self):
        return self._previewDocument

    @property
    def filename(self):
        return self._filename

    @filename.setter
    def filename(self, name):
        self._filename = name
        self.filenameChanged.emit(name)

    @property
    def changed(self):
        return self._changed

    @property
    def encoding(self):
        return self._encoding

    def onModifChange(self, changed):
        if self.changed is False and changed is True:
            self.modified.emit()

        self._changed = changed


class TextEditorTab(GalacteekTab):
    def __init__(self, editing=False, parent=None):
        super(TextEditorTab, self).__init__(parent)

        self.editor = TextEditorWidget(
            editing=editing,
            parent=self)
        self.editor.documentChanged.connect(self.onDocChange)
        self.editor.documentNameChanged.connect(self.onDocnameChanged)

        self.vLayout.addWidget(self.editor)

    def onDocChange(self, doc):
        self.changeTabName(doc.filename)

    def changeTabName(self, name):
        if name is None:
            self.setTabName(iUnknown(), widget=self)

        elif len(name) > 16:
            cutoff = int(max(
                4 * (len(name) / 5),
                len(name) / 2
            ))

            self.setTabName(
                '... {0}'.format(name[cutoff:]),
                widget=self
            )
        else:
            self.setTabName(name, widget=self)

    def onDocnameChanged(self, doc, name):
        if doc is self.editor.currentDocument:
            self.changeTabName(doc.filename)

    def onClose(self):
        if self.editor.checkChanges() is True:
            self.editor.cleanup()
            return True
        return False


class CheckoutTreeView(QTreeView):
    doubleClick = pyqtSignal(QModelIndex, QFileInfo)
    itemRightClick = pyqtSignal(QModelIndex, QMouseEvent, QFileInfo)

    def mouseDoubleClickEvent(self, event):
        idx = self.currentIndex()
        fInfo = self.model().fileInfo(idx)

        if fInfo:
            path = Path(fInfo.absoluteFilePath())
            if path.is_dir():
                super(CheckoutTreeView, self).mouseDoubleClickEvent(event)
            elif path.is_file():
                self.doubleClick.emit(idx, fInfo)

    def mousePressEvent(self, event):
        item = self.indexAt(event.pos())

        if item.isValid():
            super(CheckoutTreeView, self).mousePressEvent(event)
        else:
            self.clearSelection()

            self.selectionModel().setCurrentIndex(
                QModelIndex(),
                QItemSelectionModel.Select
            )

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.RightButton:
            idx = self.currentIndex()
            fInfo = self.model().fileInfo(idx)

            if fInfo:
                self.itemRightClick.emit(idx, event, fInfo)
        else:
            super(CheckoutTreeView, self).mouseReleaseEvent(event)


class TextEditorWidget(QWidget):
    """
    Simple Editor widget that stores the edited files in a unixfs node
    """

    rootMultihashChanged = pyqtSignal(str)
    documentChanged = pyqtSignal(Document)
    documentNameChanged = pyqtSignal(Document, str)
    filenameEntered = pyqtSignal(str)

    def __init__(self, offline=True, editing=False, sessionDagCid=None,
                 parent=None):
        super(TextEditorWidget, self).__init__(parent)

        self.app = QApplication.instance()
        self.setLayout(QVBoxLayout(self))
        self.textEditor = Editor(self)

        self.checkoutPath = None

        self.busyCube = AnimatedLabel(
            RotatingCubeRedFlash140d(speed=100),
            parent=self
        )
        self.busyCube.clip.setScaledSize(QSize(24, 24))
        self.busyCube.startClip()
        self.busyCube.hide()

        self._previewTimer = QTimer(self)
        self._previewTimer.timeout.connect(self.onPreviewRerender)
        self._editing = editing
        self._currentDocument = None
        self._unixDir = None

        self.model = QFileSystemModel()

        self.filesView = CheckoutTreeView(self)
        self.filesView.setModel(self.model)
        self.filesView.doubleClick.connect(self.onFsViewItemDoubleClicked)
        self.filesView.itemRightClick.connect(self.onFsViewRightClicked)

        self.model.setFilter(
            QDir.Files | QDir.AllDirs | QDir.NoDot | QDir.NoDotDot
        )
        self.model.setRootPath(self.checkoutPath)

        self.filesView.setVisible(False)
        self.filesView.hideColumn(1)
        self.filesView.hideColumn(2)
        self.filesView.hideColumn(3)

        self.setObjectName('textEditor')
        self.inPreview = False
        self.offline = offline

        self.editHistory = EditHistory(parent=self)
        self.editHistory.hide()
        self.copiesLayout = self.editHistory.fLayout

        self.ctrlLayout = QHBoxLayout()

        self.previewButton = CheckableToolButton(
            icon=getIcon('document-preview.png'),
            toggled=self.onPreviewToggled, parent=self
        )
        self.previewButton.setToolTip(iMarkdownPreview())

        self.fsViewButton = CheckableToolButton(
            icon=getIcon('folder-open.png'),
            toggled=self.onFsViewToggled, parent=self
        )
        self.fsViewButton.setEnabled(True)
        self.fsViewButton.setChecked(False)

        self.editButton = CheckableToolButton(
            toggled=self.onEditToggled, parent=self
        )

        self.saveButton = QToolButton(self)
        self.saveButton.setIcon(getIcon('save-file.png'))
        self.saveButton.clicked.connect(self.onSave)
        self.saveButton.setToolTip(iSave())
        self.saveButton.setEnabled(False)

        self.strokeIcon = getIcon('stroke-cube.png')

        self.editButton.setText(iEdit())

        self.unixDirCid = None
        self.unixDirDescrLabel = QLabel('Current session:')
        self.unixDirLabel = IPFSUrlLabel(
            None, invalidPathLabel='No session yet')
        self.unixDirClipButton = IPFSPathClipboardButton(None, parent=self)

        self.nameInputLabel = QLabel('File name')
        self.nameInputLine = QLineEdit('', self)
        self.nameInputLine.setMaximumWidth(160)
        self.nameInputValidate = QPushButton('OK')
        self.nameInputValidate.setMaximumWidth(40)
        self.nameInputValidate.clicked.connect(self.onNameInput)
        self.nameInputLine.returnPressed.connect(self.onNameInput)

        self.filenameEntered.connect(self.onFilenameEntered)

        self.ctrlLayout.addWidget(self.busyCube)
        self.ctrlLayout.addWidget(self.editButton)
        self.ctrlLayout.addWidget(self.previewButton)
        self.ctrlLayout.addWidget(self.fsViewButton)
        self.ctrlLayout.addWidget(self.saveButton)

        self.ctrlLayout.addWidget(self.nameInputLabel)
        self.ctrlLayout.addWidget(self.nameInputLine)
        self.ctrlLayout.addWidget(self.nameInputValidate)

        self.showNameInput(False)

        self.ctrlLayout.addItem(
            QSpacerItem(10, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.ctrlLayout.addWidget(self.unixDirDescrLabel)
        self.ctrlLayout.addWidget(self.unixDirLabel)
        self.ctrlLayout.addWidget(self.unixDirClipButton)

        self.textVLayout = QVBoxLayout()
        self.textHLayout = QHBoxLayout()
        self.textVLayout.addLayout(self.textHLayout)

        self.previewWidget = QTextEdit(self)
        self.previewWidget.hide()

        self.currentDocument = self.newDocument()
        self.textHLayout.addWidget(self.filesView)
        self.textHLayout.addWidget(self.textEditor)
        self.textHLayout.addWidget(self.previewWidget)

        optionsLayout = QHBoxLayout()
        self.tabReplaceButton = QCheckBox('Replace tabs', self)
        self.tabReplaceButton.stateChanged.connect(self.onTabReplaceToggled)
        self.tabReplaceButton.setEnabled(False)
        optionsLayout.addWidget(self.tabReplaceButton)
        self.textVLayout.addLayout(optionsLayout)

        self.layout().addLayout(self.ctrlLayout)
        self.layout().addWidget(self.editHistory)
        self.layout().addLayout(self.textVLayout)

        self.editing = editing
        self.rootMultihashChanged.connect(self.onSessionCidChanged)

        self.filesView.setMinimumWidth(self.width() / 4)

        self.textEditor.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.filesView.setSizePolicy(
            QSizePolicy.Minimum, QSizePolicy.Expanding)

    @property
    def unixDirCid(self):
        return self._unixDirCid

    @property
    def unixDir(self):
        return self._unixDir

    @unixDirCid.setter
    def unixDirCid(self, cid):
        self._unixDirCid = cid

    @property
    def editing(self):
        return self._editing

    @editing.setter
    def editing(self, editing):
        if not isinstance(editing, bool):
            return

        self._editing = editing
        self.textEditor.setReadOnly(not self.editing)
        self.editButton.setChecked(self.editing)
        self.tabReplaceButton.setEnabled(self.editing)
        self.applyStylesheet()

        if self.editing is True and self.checkoutPath is None:
            self.sessionNew()

    @property
    def currentDocument(self):
        return self._currentDocument

    @currentDocument.setter
    def currentDocument(self, doc):
        self._currentDocument = doc
        self.textEditor.setDocument(self.currentDocument)

        if self.currentDocument.filename:
            if self.currentDocument.filename.endswith('.py'):
                self.highlighter = PythonSyntaxHighlighter(
                    self.currentDocument)
                self.tabReplaceButton.setChecked(True)
            if self.currentDocument.filename.endswith('.md'):
                self.previewButton.setChecked(True)
        else:
            self.highlighter = None

        self.documentChanged.emit(self.currentDocument)
        self.currentDocument.setModified(False)

        self.currentDocument.modified.connect(
            functools.partial(self.saveButton.setEnabled, True))
        self.currentDocument.contentsChanged.connect(self.onDocumentChanged)

        self.applyStylesheet()

    async def changeDocument(self, document):
        self.textEditor.setDocument(document)

    def cleanup(self):
        if os.path.isdir(self.checkoutPath):
            log.debug('Cleaning up checkout directory: {}'.format(
                self.checkoutPath))
            shutil.rmtree(self.checkoutPath)

    def busy(self, busy=True):
        self.busyCube.setVisible(busy)
        self.setEnabled(not busy)

        if busy:
            self.busyCube.startClip()
        else:
            self.busyCube.stopClip()

    def onFsViewRightClicked(self, idx, event, fInfo):
        pos = event.globalPos()
        fullPath = fInfo.absoluteFilePath()

        menu = QMenu(self)
        menu.addAction(
            self.strokeIcon,
            'Add file', functools.partial(
                self.fsAddFile, fullPath))
        menu.addSeparator()
        menu.addAction(
            self.strokeIcon,
            'Add directory', functools.partial(
                self.fsAddDirectory, fullPath))

        menu.exec_(pos)

    def fsAddFile(self, root):
        if not root:
            rootDir = Path(self.checkoutPath)
        else:
            rootDir = Path(root)

        if not rootDir.is_dir():
            return

        name = self.nameInput()
        if name:
            filepath = rootDir.joinpath(name)
            if filepath.exists():
                return messageBox('Already exists')

            filepath.touch()
            self.sessionViewUpdate()

    def fsAddDirectory(self, root):
        if not root:
            rootDir = Path(self.checkoutPath)
        else:
            rootDir = Path(root)

        if not rootDir.is_dir():
            return

        name = self.nameInput()
        if name:
            dirpath = rootDir.joinpath(name)
            if dirpath.exists():
                return messageBox('Already exists')

            dirpath.mkdir()
            self.sessionViewUpdate()

    def onFsViewItemDoubleClicked(self, idx, fInfo):
        fullPath = fInfo.absoluteFilePath()

        if not self.checkoutPath:
            return

        if not os.path.isfile(fullPath):
            return

        filepath = re.sub(self.checkoutPath, '', fullPath).lstrip('/')
        ensure(self.openFileFromCheckout(filepath))

    def onDocumentChanged(self):
        if self.previewWidget.isVisible():
            self._previewTimer.stop()
            self._previewTimer.start(1200)

    def onPreviewRerender(self):
        self.markdownPreviewUpdate()
        self._previewTimer.stop()

    def showNameInput(self, view=True):
        self.nameInputLabel.setVisible(view)
        self.nameInputLine.setVisible(view)
        self.nameInputValidate.setVisible(view)

        if view is False:
            self.nameInputLine.clear()

        if view is True:
            self.nameInputLine.setFocus(Qt.OtherFocusReason)

    def onTabReplaceToggled(self, state):
        self.textEditor.tabReplace = state

    def onNameInput(self):
        filename = self.nameInputLine.text()
        if len(filename) > 0:
            self.filenameEntered.emit(filename)

    def onFilenameEntered(self, filename):
        if self.currentDocument:
            self.currentDocument.filename = filename
            self.currentDocument.filenameChanged.emit(filename)

            self.documentNameChanged.emit(self.currentDocument, filename)
            self.showNameInput(False)
            ensure(self.saveDocument(self.currentDocument))

    def onDocnameChanged(self, doc, name):
        if doc == self.currentDocument:
            self.setTabName(name, widget=self)

    def applyStylesheet(self):
        if self.editing is True:
            self.textEditor.setStyleSheet('''
                QPlainTextEdit {
                    background-color: #D2DBD6;
                    color: #242424;
                    padding: 5px;
                    font: 14pt "Courier";
                    font-weight: bold;
                }
            ''')
            self.textEditor.connectSignals()
        else:
            self.textEditor.highlightCurrentLine()
            self.textEditor.setStyleSheet(defaultStyleSheet)

    def display(self, ipfsPath):
        if not isinstance(ipfsPath, IPFSPath) or not ipfsPath.valid:
            return

        ensure(self.showFromPath(ipfsPath))

    def genUid(self):
        return str(uuid.uuid4())

    def newDocument(self, name=None, text='', encoding='utf-8',
                    textLayout=True):
        self.textEditor.setStyleSheet(defaultStyleSheet)
        return Document(name=name, text=text, parent=self, encoding=encoding,
                        textLayout=textLayout)

    def markdownPreviewUpdate(self):
        textData = self.currentDocument.toPlainText()
        pDocument = self.previewWidget.document()

        try:
            html = markitdown(textData)
            pDocument.setHtml(html)
        except Exception:
            pDocument.setPlainText(textData)

    def showPreview(self):
        textData = self.currentDocument.toPlainText()
        previewName = None

        if self.currentDocument.filename and \
                self.currentDocument.filename.endswith('.md'):
            previewName = self.currentDocument.filename.replace(
                '.md', '.html')

        newDocument = self.newDocument(
            name=previewName, text=textData,
            textLayout=False
        )

        try:
            html = markitdown(textData)
            newDocument.setHtml(html)
            self.currentDocument._previewDocument = newDocument
        except Exception:
            newDocument.setPlainText(textData)

        self.previewWidget.setDocument(newDocument)
        self.previewWidget.setReadOnly(True)
        self.previewWidget.show()

    def showText(self, textData, preview=False):
        if preview:
            text = textData
            newDocument = self.newDocument(text=textData)

            try:
                html = markitdown(text)
                newDocument.setHtml(html)
            except Exception:
                newDocument.setPlainText(text)

            self.textEditor.setReadOnly(True)
            return newDocument
        else:
            doc = self.newDocument(text=textData)
            self.textEditor.setReadOnly(not self.editing)
            return doc

    def onFsViewToggled(self, checked):
        self.toggleFsView(checked)

    def toggleFsView(self, view):
        if self.filesView:
            self.filesView.setVisible(view)

    def onSave(self):
        if self.currentDocument.filename is None:
            self.showNameInput(True)
        else:
            ensure(self.saveDocument(self.currentDocument))

    def nameInput(self, label='File name'):
        name = inputText(label=label)
        if name and len(name) in range(1, 256):
            return name

    def checkChanges(self):
        if self.currentDocument and self.currentDocument.changed is True:
            reply = questionBox(
                'Unsaved changes',
                'The current document was not saved, continue ?')
            return reply
        return True

    def onNewFile(self):
        if not self.checkChanges():
            return

        name = self.nameInput()

        if name:
            self.currentDocument = self.newDocument(name=name)
            self.editing = True

    def onEditToggled(self, checked):
        self.editing = checked

    def onPreviewToggled(self, checked):
        self.inPreview = checked

        if checked:
            self.showPreview()
        else:
            self.previewWidget.hide()

    def onSessionCidChanged(self, cid):
        log.debug('Session now at CID: {}'.format(cid))
        self.unixDirCid = cid
        self.unixDirPath = IPFSPath(cid)
        self.unixDirLabel.path = self.unixDirPath
        self.unixDirClipButton.path = self.unixDirPath

    def sessionViewUpdate(self, root=None):
        path = root if root else self.checkoutPath
        self.model.setRootPath(path)
        self.filesView.setRootIndex(self.model.index(path))

    # @ipfsOp
    def sessionNew(self):
        localDirName = self.genUid()
        localPath = os.path.join(
            self.app.tempDir.path(), localDirName)

        if not os.path.exists(localPath):
            try:
                os.mkdir(localPath)
            except:
                pass

        ensure(self.sync())
        self.sessionViewUpdate(localPath)
        self.checkoutPath = localPath
        return localPath

    def makeDatetime(self, date=None):
        datet = date if date else datetime.now()
        return isoformat(datet)

    @ipfsOp
    async def sync(self, ipfsop):
        try:
            async with ipfsop.offlineMode() as opoff:
                entry = await opoff.addPath(self.checkoutPath, wrap=False,
                                            hidden=True)
        except Exception as err:
            log.debug(str(err))
        else:
            if not entry:
                return

            self.rootMultihashChanged.emit(entry['Hash'])
            return entry

    @ipfsOp
    async def saveDocument(self, ipfsop, document, offline=True):
        text = document.toPlainText()

        if not document.filename:
            return

        docPath = os.path.join(self.checkoutPath, document.filename)
        async with aiofiles.open(docPath, 'w+t') as fd:
            await fd.write(text)

        if document.previewDocument:
            pPath = os.path.join(self.checkoutPath,
                                 document.previewDocument.filename)
            text = document.previewDocument.toHtml()
            async with aiofiles.open(pPath, 'w+t') as fd:
                await fd.write(text)

        document.setModified(False)
        self.saveButton.setEnabled(False)

        self.sessionViewUpdate(self.checkoutPath)

        entry = await self.sync()
        if entry:
            layout = QHBoxLayout()
            path = IPFSPath(entry['Hash'])

            urlLabel = IPFSUrlLabel(path)
            clipButton = IPFSPathClipboardButton(path)

            now = QDateTime.currentDateTime()
            date = QLabel()
            date.setText(now.toString('hh:mm:ss'))

            publishButton = QToolButton()
            publishButton.setText('Publish')
            publishButton.clicked.connect(functools.partial(
                self.onPublishFile, entry, publishButton))

            layout.addWidget(date)
            layout.addWidget(urlLabel)
            layout.addWidget(clipButton)
            layout.addItem(QSpacerItem(10, 10, QSizePolicy.Expanding,
                                       QSizePolicy.Minimum))
            layout.addWidget(publishButton)

            self.copiesLayout.insertLayout(0, layout)
            self.editHistory.show()

    @ipfsOp
    async def publishEntry(self, ipfsop, entry):
        log.debug('Publishing {}'.format(entry))
        try:
            async for msg in ipfsop.client.dht.provide(entry['Hash']):
                log.debug('Provide result: {}'.format(msg))
        except Exception as err:
            messageBox('Could not publish')
            log.debug(str(err))
            return False
        else:
            return True

    def onPublishFile(self, entry, pButton):
        def finished(future):
            try:
                result = future.result()
                if result is True:
                    pButton.setEnabled(False)
                    pButton.setText('Published')
            except:
                pButton.setText('ERR')

        ensure(self.publishEntry(entry),
               futcallback=finished)

    @ipfsOp
    async def showFromPath(self, ipfsop, ipfsPath):
        if not self.checkChanges():
            return

        if not ipfsPath.valid:
            return

        self.busy()

        try:
            dstdir = self.sessionNew()
            mimeType, stat = await self.app.rscAnalyzer(ipfsPath)

            if not stat:
                self.busy(False)
                messageBox('Stat failed')

            sInfo = StatInfo(stat)
            if sInfo.totalSize > megabytes(32):
                if not questionBox(
                        'Stat size', 'Large object, fetch anyway ?'):
                    self.busy(False)
                    raise Exception('Object too large')

            if not await ipfsop.client.get(
                ipfsPath.objPath,
                dstdir=dstdir
            ):
                raise Exception('Fetch failed')
        except Exception as err:
            self.busy(False)
            messageBox('Error fetching object: {}'.format(str(err)))
        else:
            rooted = os.path.join(dstdir, ipfsPath.basename)

            if os.path.isdir(rooted):
                path = rooted
            elif os.path.isfile(rooted):
                path = dstdir
            else:
                path = dstdir

            self.checkoutPath = path
            self.sessionViewUpdate(self.checkoutPath)

            for file in os.listdir(self.checkoutPath):
                fp = os.path.join(self.checkoutPath, file)
                mtype = await detectMimeTypeFromFile(fp)

                if mtype and (mtype.isText or mtype.isHtml):
                    await self.openFileFromCheckout(file)
                    break

            self.fsViewButton.setChecked(True)

        self.busy(False)

    async def isTextFile(self, path):
        mtype = await detectMimeTypeFromFile(path)
        return mtype and (mtype.isText or mtype.isHtml)

    async def openFileFromCheckout(self, relpath):
        if not self.checkChanges():
            return

        self.previewButton.setChecked(False)
        fp = Path(os.path.join(self.checkoutPath, relpath))

        if not fp.exists():
            return

        fsize = fp.stat().st_size

        if fsize > 0 and not await self.isTextFile(str(fp)):
            return messageBox('Not a text file')

        self.busy()

        basename = relpath
        doc = self.newDocument(name=basename)
        cursor = QTextCursor(doc)

        async for chunk in asyncReadTextFileChunked(
                str(fp), mode='rt'):
            await asyncio.sleep(0.1)
            cursor.insertText(chunk)

        self.currentDocument = doc
        self.busy(False)
        return doc

    def decode(self, data):
        for enc in ['utf-8', 'latin1', 'ascii']:
            try:
                textData = data.decode(enc)
            except BaseException:
                continue
            else:
                return enc, textData
        return None, None
