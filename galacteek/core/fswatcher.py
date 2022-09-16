from pathlib import Path
import os
import asyncio

from galacteek.core.asynclib import loopTime

from PyQt5.QtCore import QFileSystemWatcher
from PyQt5.QtCore import QObject
from PyQt5.QtCore import pyqtSignal


class FileWatcher(QObject):
    """
    Wrapper around QFileSystemWatcher.

    The bufferMs (in milliseconds) parameter controls the time
    window for which we'll ignore subsequent changes in the files
    we monitor (if a file change occurs soon after another change).

    The pathChanged signal is called after the specified delay
    (seconds)
    """
    pathChanged = pyqtSignal(str)

    def __init__(self, bufferMs=1000, delay=0, parent=None):
        super().__init__(parent)

        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self.onChanged)
        self._watcher.fileChanged.connect(self.onChanged)
        self._events = {}
        self._buffer = bufferMs
        self._delay = delay
        self._emitLast = 0

    @property
    def watched(self):
        return self._watcher.directories() + self._watcher.files()

    def clear(self):
        if len(self.watched) > 0:
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
        loop = asyncio.get_event_loop()

        if self._emitLast == 0 or loopTime() - self._emitLast > \
                (self._buffer / 1000):
            loop.call_later(self._delay, self.pathChanged.emit, path)
            self._emitLast = loopTime()
