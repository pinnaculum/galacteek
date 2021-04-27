import asyncio

from PyQt5.QtCore import QObject

from galacteek.core.asynclib import threadedCoro


class AsyncChanObject(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.loop = asyncio.SelectorEventLoop()

    def tc(self, coro, *args):
        return threadedCoro(self.loop, coro, *args)
