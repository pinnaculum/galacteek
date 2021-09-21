import asyncio

from PyQt5.QtCore import QObject
from PyQt5.QtCore import QJsonValue

from galacteek.core.asynclib import threadedCoro


class AsyncChanObject(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.loop = asyncio.SelectorEventLoop()

    def tc(self, coro, *args):
        return threadedCoro(self.loop, coro, *args)

    def _dict(self, obj):
        if isinstance(obj, dict):
            return obj
        elif isinstance(obj, QJsonValue):
            return obj.toVariant()
        else:
            return None
