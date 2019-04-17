from PyQt5.QtCore import QFileSystemWatcher
from PyQt5.QtCore import QObject
from PyQt5.QtCore import pyqtSignal


class FileWatcher(QObject):
    pathChanged = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self.onChanged)
        self._watcher.fileChanged.connect(self.onChanged)
        self._events = {}

    @property
    def watched(self):
        return self._watcher.directories() + self._watcher.files()

    def watch(self, path):
        self._watcher.addPath(path)

    def onChanged(self, path):
        self.pathChanged.emit(path)
