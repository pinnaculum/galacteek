import traceback

from logbook import Handler

from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtWidgets import QToolBar
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QTextEdit
from PyQt5.QtWidgets import QLineEdit

from PyQt5.QtCore import Qt

from PyQt5.Qt import QSizePolicy

from PyQt5.QtGui import QTextCursor
from PyQt5.QtGui import QTextDocument

from galacteek.core.glogger import LogRecordStyler
from galacteek.core.modelhelpers import *
from galacteek.ipfs.wrappers import *
from galacteek.ipfs.ipfsops import *


class UserLogsWindow(QMainWindow):
    hidden = pyqtSignal()

    def __init__(self):
        super(UserLogsWindow, self).__init__()
        self.toolbar = QToolBar(self)
        self.toolbar.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)

        self.logsBrowser = QTextEdit(self)
        self.logsBrowser.setFontPointSize(16)
        self.logsBrowser.setReadOnly(True)
        self.logsBrowser.setObjectName('logsTextWidget')
        self.logsBrowser.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.searchBack = QPushButton('Search backward')
        self.searchBack.clicked.connect(self.onSearchBack)
        self.searchFor = QPushButton('Search forward')
        self.searchFor.clicked.connect(self.onSearchForward)

        self.logsSearcher = QLineEdit(self)
        self.logsSearcher.setClearButtonEnabled(True)
        self.toolbar.addWidget(self.logsSearcher)
        self.toolbar.addWidget(self.searchBack)
        self.toolbar.addWidget(self.searchFor)
        self.logsSearcher.returnPressed.connect(self.onSearchBack)
        self.logsSearcher.textChanged.connect(self.onSearchTextChanged)
        self.setCentralWidget(self.logsBrowser)

    def onSearchTextChanged(self):
        pass

    def onSearchBack(self):
        flags = QTextDocument.FindCaseSensitively | QTextDocument.FindBackward
        self.searchText(flags)

    def onSearchForward(self):
        flags = QTextDocument.FindCaseSensitively
        self.searchText(flags)

    def searchText(self, flags):
        text = self.logsSearcher.text()
        if text:
            self.logsBrowser.find(text, flags)

    def hideEvent(self, event):
        self.hidden.emit()
        super().hideEvent(event)


class MainWindowLogHandler(Handler):
    """
    Custom logbook handler that logs to the status bar

    Should be moved to a separate module
    """

    modulesColorTable = {
        'galacteek.ui.resource': '#7f8491',
        'galacteek.did.ipid': '#7f8491',
        'galacteek.core.profile': 'blue',
        'galacteek.ui.chat': 'blue'
    }

    def __init__(self, logsBrowser, application_name=None, address=None,
                 facility='user', level=0, format_string=None,
                 filter=None, bubble=True, window=None):
        Handler.__init__(self, level, filter, bubble)
        self.app = QApplication.instance()
        self.application_name = application_name
        self.window = window
        self.logsBrowser = logsBrowser
        self.logsBrowser.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.doc = self.logsBrowser.document()
        self.logStyler = LogRecordStyler()

    def emit(self, record):
        # The emit could be called from another thread so play it safe ..
        if not self.app.shuttingDown:
            self.app.loop.call_soon_threadsafe(self._handleRecord, record)

    def _handleRecord(self, record):
        try:
            cursor = self.logsBrowser.textCursor()
            vScrollBar = self.logsBrowser.verticalScrollBar()
            color, _font = self.logStyler.getStyle(record)

            if record.level_name == 'INFO':
                self.window.statusMessage(
                    f'''
                    <div style="width: 450px">
                      <p style="color: {color}">
                        <b>{record.module}</b>
                      </p>
                      <p>{record.message}</p>
                    </div>
                    '''
                )

            oldScrollbarValue = vScrollBar.value()
            isDown = oldScrollbarValue == vScrollBar.maximum()

            self.logsBrowser.moveCursor(QTextCursor.End)
            self.logsBrowser.insertHtml(
                f'''
                <p style="color: {color}; font: 14pt 'Inter UI';">
                    [{record.time:%H:%M:%S.%f%z}]
                    <b>@{record.module}@</b>: {record.message}
                </p>
                <br />
                '''
            )

            if cursor.hasSelection() or not isDown:
                self.logsBrowser.setTextCursor(cursor)
                vScrollBar.setValue(oldScrollbarValue)
            else:
                self.logsBrowser.moveCursor(QTextCursor.End)
                vScrollBar.setValue(vScrollBar.maximum())

            if self.doc.lineCount() > 2048:
                self.doc.clear()
        except Exception:
            traceback.print_exc()
