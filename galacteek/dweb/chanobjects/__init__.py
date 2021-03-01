from PyQt5.QtCore import QObject

from galacteek.core.asynclib import threadedCoro


class AsyncChanObject(QObject):
    def tc(self, coro, *args):
        return threadedCoro(coro, args)
