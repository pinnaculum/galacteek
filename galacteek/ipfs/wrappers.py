
import functools

from PyQt5.QtWidgets import QApplication

from galacteek.ipfs.ipfsops import *

def _getOp():
    app = QApplication.instance()
    if not app:
        raise Exception('No Application')
    return app.getIpfsOperator()

def appTask(fn, *args, **kw):
    app = QApplication.instance()
    app.task(fn, *args, **kw)

def ipfsFunc(func):
    @functools.wraps(func)
    async def wrapper(*args, **kw):
        app = QApplication.instance()
        if not app:
            raise Exception('No Application')
        return await func(app.ipfsClient, *args, **kw)
    return wrapper

def ipfsOpFn(func):
    @functools.wraps(func)
    async def wrapper(*args, **kw):
        op = _getOp()
        return await func(op, *args, **kw)
    return wrapper

class ipfsClassW:
    def __init__(self, wrapped):
        self.wrapped = wrapped
        self.name = wrapped.__name__

class ipfsOp(ipfsClassW):
    """
    Wraps an async class method, calling it with an IPFSOperator
    Requires prior instantiation of a GalacteekApplication
    """
    def __get__(self, inst, owner):
        async def wrapper(*args, **kw):
            op = _getOp()
            return await self.wrapped(inst, op, *args, **kw)
        return wrapper

class ipfsStatOp(ipfsClassW):
    def __get__(self, inst, owner):
        async def wrapper(*args, **kw):
            op = _getOp()
            path = args[0]

            stat = op.objStatCtxGet(path)
            if not stat:
                stat = await op.objStatCtxUpdate(path)

            args = args + (stat,)

            return await self.wrapped(inst, op, *args, **kw)
        return wrapper
