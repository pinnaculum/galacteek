import time
import collections

from PyQt5.QtGui import QIcon, QClipboard
from PyQt5.QtCore import (
    QCoreApplication,
    QUrl,
    pyqtSignal,
    QDateTime,
    QObject)

from galacteek.ipfs import asyncipfsd, cidhelpers
from galacteek.ipfs.ipfsops import joinIpfs


class ClipboardTracker(QObject):
    """
    Tracks the system's clipboard activity and emits signals
    depending on whether or not the clipboard contains an IPFS CID or path
    """
    clipboardHasIpfs = pyqtSignal(bool, str, str)
    clipboardHistoryChanged = pyqtSignal(dict)

    def __init__(self, clipboard):
        super(ClipboardTracker, self).__init__()

        self.hasIpfs = False
        self.history = {}
        self.clipboard = clipboard
        self.clipboard.changed.connect(self.onClipboardChanged)
        self.clipboardHasIpfs.connect(self.onHasIpfs)

    def onClipboardChanged(self, mode):
        text = self.clipboard.text(mode)
        self.clipboardProcess(text, clipboardMode=mode)

    def clipboardProcess(self, text, clipboardMode=None):
        """
        Process the contents of the clipboard. If it is a valid CID/path,
        emit a signal, processed by the main window for the clipboard
        loader button
        """
        if not text or len(text) > 1024:  # that shouldn't be worth handling
            return

        text = text.strip()
        ma = cidhelpers.ipfsRegSearchPath(text)

        if ma:
            # The clipboard contains a full IPFS path
            cid = ma.group('cid')
            if not cidhelpers.cidValid(cid):
                return
            path = ma.group('fullpath')
            self.hRecord(path)
            return self.clipboardHasIpfs.emit(True, cid, path)

        ma = cidhelpers.ipnsRegSearchPath(text)
        if ma:
            # The clipboard contains a full IPNS path
            path = ma.group('fullpath')
            self.hRecord(path)
            return self.clipboardHasIpfs.emit(True, None, path)

        ma = cidhelpers.ipfsRegSearchCid(text)
        if ma:
            # The clipboard simply contains a CID
            cid = ma.group('cid')
            if not cidhelpers.cidValid(cid):
                return

            cidObject = cidhelpers.getCID(cid)
            if cidObject.version == 1:
                cidB32 = cidhelpers.cidConvertBase32(cid)
                if cidB32:
                    path = joinIpfs(cidB32)
            else:
                path = joinIpfs(cid)

            self.hRecord(path)
            return self.clipboardHasIpfs.emit(True, cid, path)

        # Not a CID/path
        if clipboardMode == self.clipboardPreferredMode():
            self.clipboardHasIpfs.emit(False, None, None)

    def hLookup(self, path):
        for hTs, hItem in self.history.items():
            if hItem['path'] == path:
                return hTs, hItem

    def hRecord(self, path):
        """ Records an item in the history and emits a signal """
        now = time.time()
        self.history[now] = {
            'path': path,
            'date': QDateTime.currentDateTime()
        }
        self.clipboardHistoryChanged.emit(self.getHistory())

    def getHistory(self):
        return collections.OrderedDict(sorted(self.history.items(),
                                              key=lambda t: t[0]))

    def clearHistory(self):
        self.history = {}
        self.clipboardHistoryChanged.emit(self.getHistory())

    def getHistoryLatest(self):
        """ Returns latest history item """
        h = self.getHistory()
        try:
            return h.popitem(last=True)[1]
        except KeyError:
            return None

    def getCurrent(self):
        """ Returns current clipboard item """
        if self.hasIpfs:
            return self.getHistoryLatest()

    def clipboardInit(self):
        """ Used to process the clipboard's content on application's init """
        text = self.getText()
        self.clipboardProcess(text)

    def clipboardPreferredMode(self):
        return QClipboard.Selection if self.clipboard.supportsSelection() \
            else QClipboard.Clipboard

    def setText(self, text):
        """ Sets the clipboard's text content """
        self.clipboard.setText(text, self.clipboardPreferredMode())

    def getText(self):
        """ Returns clipboard's text content from the preferred source """
        return self.clipboard.text(self.clipboardPreferredMode())

    def onHasIpfs(self, valid, cid, path):
        self.hasIpfs = valid
