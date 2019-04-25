import os.path
import time
import collections

from PyQt5.QtGui import QClipboard
from PyQt5.QtCore import QObject
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QDateTime

from galacteek import ensure
from galacteek import log
from galacteek.ipfs import cidhelpers
from galacteek.ipfs import ipfsOp
from galacteek.ipfs.cidhelpers import joinIpfs
from galacteek.ipfs.mimetype import detectMimeType
from galacteek.ipfs.mimetype import MIMEType


class ClipboardItem(QObject):
    mimeTypeDetected = pyqtSignal(MIMEType)
    mimeTypeAvailable = pyqtSignal(MIMEType)
    mimeIconAvailable = pyqtSignal()
    statRetrieved = pyqtSignal(dict)

    def __init__(self, input, rscPath, mimeType=None, parent=None):
        super(ClipboardItem, self).__init__(parent)

        self._clipInput = input
        self._path = rscPath
        self._mimeType = mimeType
        self._statInfo = None
        self._cid = None
        self._ts = time.time()
        self._date = QDateTime.currentDateTime()
        self._mimeIcon = None

        self.mimeTypeDetected.connect(self.setMimeType)
        self.statRetrieved.connect(self.statInfo)

    @property
    def ts(self):
        return self._ts

    @property
    def date(self):
        return self._date

    @property
    def path(self):
        return self._path

    @property
    def basename(self):
        return os.path.basename(self.path)

    @property
    def cid(self):
        return self._cid

    @property
    def mimeType(self):
        return self._mimeType

    @property
    def mimeCategory(self):
        if isinstance(self.mimeType, MIMEType):
            return self.mimeType.category

    @property
    def mimeIcon(self):
        return self._mimeIcon

    @mimeIcon.setter
    def mimeIcon(self, icon):
        self._mimeIcon = icon
        self.mimeIconAvailable.emit()

    @property
    def stat(self):
        return self._statInfo

    @property
    def clipInput(self):
        return self._clipInput

    @property
    def valid(self):
        return isinstance(self.mimeType, MIMEType) and self.stat is not None

    def setMimeType(self, mimeType):
        log.debug('Detected mime-type {type} for {path}'.format(
            path=self.path, type=str(mimeType)))
        self._mimeType = mimeType
        self.mimeTypeAvailable.emit(mimeType)

    def statInfo(self, stat):
        self._statInfo = stat
        self._cid = stat.get('Hash', None)

    def __str__(self):
        return self.path

    def __repr__(self):
        return '{ts} {path}: mime {mimetype}, stat {stat}'.format(
            ts=self.ts,
            path=self.path,
            mimetype=self.mimeType,
            stat=self.stat
        )


class ClipboardTracker(QObject):
    """
    Tracks the system's clipboard activity and emits signals
    depending on whether or not the clipboard contains an IPFS CID or path
    """

    clipboardHasIpfs = pyqtSignal(bool, str)
    clipboardHistoryChanged = pyqtSignal()  # not used anymore

    itemRegister = pyqtSignal(ClipboardItem, bool)
    itemAdded = pyqtSignal(ClipboardItem)
    itemRemoved = pyqtSignal(ClipboardItem)
    currentItemChanged = pyqtSignal(ClipboardItem)

    def __init__(self, app, clipboard):
        super(ClipboardTracker, self).__init__()

        self.app = app
        self.clipboard = clipboard
        self.hasIpfs = False
        self.history = {}

        self._current = None
        self._items = collections.deque(maxlen=128)
        self.itemRegister.connect(self.addItem)

        self.clipboard.changed.connect(self.onClipboardChanged)
        self.clipboardHasIpfs.connect(self.onHasIpfs)

    @property
    def items(self):
        return self._items

    @property
    def current(self):
        return self._current

    @current.setter
    def current(self, item):
        self._current = item
        self.currentItemChanged.emit(item)

        if item.mimeType:
            item.mimeTypeAvailable.emit(item.mimeType)

    def __len__(self):
        return len(self.items)

    def addItem(self, obj, setToCurrent):
        self._items.append(obj)

        if setToCurrent:
            self.current = obj

        self.itemAdded.emit(obj)

    def exists(self, rscPath):
        for obj in self.items:
            if obj.path == rscPath:
                return True
        return False

    def getByPath(self, rscPath):
        for obj in self.items:
            if obj.path == rscPath:
                return obj

    def removeItem(self, item):
        if self.exists(item.path):
            try:
                self.items.remove(item)
                self.itemRemoved.emit(item)
            except BaseException:
                return

    def onClipboardChanged(self, mode):
        text = self.clipboard.text(mode)
        self.clipboardProcess(text, clipboardMode=mode)

    def clipboardProcess(self, text, clipboardMode=None):
        """
        Process the contents of the clipboard. If it is a valid CID/path,
        emit a signal, processed by the main window for the clipboard
        loader button
        """
        enableBase32 = False
        if not text or len(text) > 1024:  # that shouldn't be worth handling
            return

        text = text.strip().rstrip('/')
        ma = cidhelpers.ipfsRegSearchPath(text)

        if ma:
            # The clipboard contains a full IPFS path
            cid = ma.group('cid')
            if not cidhelpers.cidValid(cid):
                return
            path = ma.group('fullpath')
            return self.clipboardHasIpfs.emit(True, path)

        ma = cidhelpers.ipnsRegSearchPath(text)
        if ma:
            # The clipboard contains a full IPNS path
            path = ma.group('fullpath')
            return self.clipboardHasIpfs.emit(True, path)

        ma = cidhelpers.ipfsRegSearchCid(text)
        if ma:
            # The clipboard simply contains a CID
            cid = ma.group('cid')
            if not cidhelpers.cidValid(cid):
                return

            cidObject = cidhelpers.getCID(cid)
            if cidObject.version == 1 and enableBase32:
                cidB32 = cidhelpers.cidConvertBase32(cid)
                if cidB32:
                    path = joinIpfs(cidB32)
            else:
                path = joinIpfs(cid)

            return self.clipboardHasIpfs.emit(True, path)

        # Not a CID/path
        if clipboardMode == self.clipboardPreferredMode():
            self.clipboardHasIpfs.emit(False, None)

    def getHistory(self):
        return list(self.items)

    def clearHistory(self):
        for item in self._items:
            self.itemRemoved.emit(item)
        self._items.clear()

    def getCurrent(self):
        """ Returns current clipboard item """
        return self.current

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

    def onHasIpfs(self, valid, path):
        self.hasIpfs = valid
        if not valid:
            return

        exists = self.exists(path)

        if exists is False:
            item = ClipboardItem(None, path)
            self.itemRegister.emit(item, True)

            if valid is True and path:
                ensure(self.scanItem(item))
        else:
            # Find the existing item by its path and set as current item
            item = self.getByPath(path)
            if item:
                self.current = item

    @ipfsOp
    async def scanItem(self, ipfsop, cItem):
        mimetype = None
        path = cItem.path
        mHashMeta = await self.app.multihashDb.get(path)

        if mHashMeta:
            # Already have metadata for this object
            value = mHashMeta.get('mimetype')
            if value:
                mimetype = MIMEType(value)

            statInfo = mHashMeta.get('stat')
            if statInfo:
                cItem.statRetrieved.emit(statInfo)
        else:
            mimetype = await detectMimeType(path)

            statInfo = await ipfsop.objStat(path)
            if not statInfo or not isinstance(statInfo, dict):
                log.debug('Stat failed for {path}'.format(
                    path=path))
                return
            else:
                cItem.statRetrieved.emit(statInfo)

            await ipfsop.sleep()

            # Store retrieved information in the metadata store
            metadata = {}

            if mimetype and mimetype.valid:
                metadata['mimetype'] = str(mimetype)
            if statInfo and isinstance(statInfo, dict):
                metadata['stat'] = statInfo

            if len(metadata) > 0:
                await self.app.multihashDb.store(
                    path,
                    **metadata
                )

        if mimetype and mimetype.valid:
            cItem.mimeTypeDetected.emit(mimetype)
