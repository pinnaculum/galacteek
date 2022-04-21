from pathlib import Path
import os

from PyQt5.QtCore import QFileSystemWatcher
from PyQt5.QtCore import QObject
from PyQt5.QtCore import pyqtSignal


class FileWatcher(QObject):
    pathChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self.onChanged)
        self._watcher.fileChanged.connect(self.onChanged)
        self._events = {}

    @property
    def watched(self):
        return self._watcher.directories() + self._watcher.files()

    def clear(self):
        self._watcher.removePaths(self.watched)

    def watch(self, path):
        self._watcher.addPath(path)

    def watchWalk(self, path: Path):
        try:
            for root, dirs, files in os.walk(str(path)):
                for dir in dirs:
                    self._watcher.addPath(str(
                        Path(root).joinpath(dir)
                    ))

                for file in files:
                    self._watcher.addPath(str(
                        Path(root).joinpath(file)
                    ))
        except Exception:
            pass

    def onChanged(self, path):
        self.pathChanged.emit(path)
