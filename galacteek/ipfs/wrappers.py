
import functools

from PyQt5.QtWidgets import QApplication

from galacteek.ipfs.ipfsops import *

def ipfsFunc(func):
    @functools.wraps(func)
    async def wrapper(*args, **kw):
        app = QApplication.instance()
        if not app:
            raise Exception('Application is gone')
        client = app.getIpfsClient()
        return await func(client, *args, **kw)
    return wrapper

class ipfsOp:
    """
    Wraps an async class method, calling it with an IPFSOperator
    Requires prior instantiation of a GalacteekApplication
    """
    def __init__(self, wrapped):
        self.wrapped = wrapped
        self.name = wrapped.__name__

    def __get__(self, inst, owner):
        async def wrapper(*args, **kw):
            app = QApplication.instance()
            if not app:
                raise Exception('Application is gone')
            client = app.getIpfsClient()
            op = IPFSOperator(client, ctx=app.ipfsCtx, debug=app.debugEnabled)
            return await self.wrapped(inst, op, *args, **kw)
        return wrapper
