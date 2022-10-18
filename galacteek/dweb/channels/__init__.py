import asyncio
import secrets
import functools
import traceback

from PyQt5.QtCore import QObject
from PyQt5.QtCore import QVariant
from PyQt5.QtCore import QJsonValue
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import pyqtProperty

from galacteek import services
from galacteek.core import runningApp
from galacteek.core.asynclib import threadedCoro
from galacteek.core.asynclib import threadedCoroWithApp
from galacteek.core.asynclib import threadExec


def opSlot(*args, **kws):
    result = kws.pop('result', QVariant)

    def _error_handler(task):
        try:
            res = task.result()

            if result is QVariant:
                # Convert explicitely as QVariant (should be dict)
                try:
                    value = QVariant(res)
                except Exception:
                    value = QVariant({})
            else:
                value = res

            task._obj.opDone.emit(
                task._tid,
                value
            )
        except RuntimeError:
            # Wrapped object probably deleted
            pass
        except Exception:
            traceback.print_exc()

    def outer_decorator(fn):
        @pyqtSlot(*args, result=result)
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            obj = args[0]

            task = asyncio.ensure_future(
                fn(*args, **kwargs)
            )
            task._tid = secrets.token_hex(16)
            task._obj = obj
            # task._fnName = fn.__name__

            task.add_done_callback(_error_handler)
            return task._tid

        return wrapper

    return outer_decorator


def tcSlot(*args, **kws):
    result = kws.pop('result', QVariant)

    def outer_decorator(fn):
        @pyqtSlot(*args, result=result)
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            obj = args[0]
            res = obj.tcRaw(fn, *args)

            if result is QVariant:
                try:
                    value = QVariant(res)
                except Exception:
                    value = QVariant({})
            else:
                value = res

            return value

        return wrapper

    return outer_decorator


class GAsyncObject(QObject):
    opDone = pyqtSignal(str, QVariant)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.loop = asyncio.SelectorEventLoop()
        self.app = runningApp()

    @tcSlot()
    async def close(self):
        op = self.ipfsOpGet()
        if op:
            await op.client.close()

    def ipfsOpGet(self):
        return self.app.ipfsOperatorForLoop(self.loop)

    def secret(self):
        return secrets.token_hex(12)

    def tc(self, coro, *args):
        return threadedCoroWithApp(self.loop, coro, *args)

    def tcRaw(self, coro, *args):
        return threadedCoro(self.loop, coro, *args)

    async def tExec(self, fn, *args):
        await threadExec(fn, *args)

    def _dict(self, obj):
        if isinstance(obj, dict):
            return obj
        elif isinstance(obj, QJsonValue):
            return obj.toVariant()
        else:
            return {}


class GOntoloObject(GAsyncObject):
    def __init__(self, parent=None, **kw):
        super().__init__(parent)

        self._chainUri = ''
        self._graphUri = 'urn:ipg:i:i0'

    @property
    def pronto(self):
        return services.getByDotName('ld.pronto')

    @pyqtProperty(str)
    def graphUri(self):
        return self._graphUri

    @graphUri.setter
    def graphUri(self, uri):
        self._graphUri = uri

    @pyqtProperty(str)
    def chainUri(self):
        return self._chainUri

    @chainUri.setter
    def chainUri(self, uri):
        self._chainUri = uri

    @property
    def _graph(self):
        return self.pronto.graphByUri(self._graphUri)

    def g(self):
        return self.pronto.graphByUri(self._graphUri)


class GServiceQtApi(GAsyncObject):
    def __init__(self, service, *args, **kw):
        super().__init__(*args, **kw)

        self.service = service
