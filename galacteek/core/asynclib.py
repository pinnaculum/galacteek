import os.path
from collections import UserList
from collections import deque
from typing import Deque
from asyncqt import QThreadExecutor
import concurrent.futures
import threading
import asyncio
import shutil
import traceback
import functools
from asyncio_extras.file import open_async
import aiofiles
import aiohttp
from aiohttp_socks import ProxyConnector


from PyQt5.QtWidgets import QApplication


class AsyncSignal(UserList):
    """
    Async signal.

    Similar to aiohttp.Signal but no need to freeze the
    callback list. Adding signals works by just using append()
    """

    def __init__(self, *signature, **kw):
        super().__init__()
        self.eventFired = asyncio.Event()

        self._id = kw.pop('_id', 'No ID')
        self._sig = signature
        self._loop = asyncio.get_event_loop()  # loop attached to this signal
        self._emitCount = 0

    def __str__(self):
        return '<AsyncSignal({id}): signature: {!r}>'.format(
            list(self._sig), id='no id')

    def count(self):
        return len(self)

    def disconnect(self, cbk):
        try:
            for receiver in self:
                if receiver == cbk:
                    self.remove(cbk)
        except Exception:
            pass

    def connectTo(self, callback):
        self.append(callback)

    def emitSafe(self, *args, **kwargs):
        asyncio.run_coroutine_threadsafe(
            self.emit(*args, **kwargs),
            self._loop
        )

    async def fire(self):
        from galacteek import log
        try:
            self.eventFired.clear()
            self.eventFired.set()
        except Exception as err:
            log.debug(f'Could not fire signal event: {err}')

    async def emit(self, *args, **kwargs):
        from galacteek import log

        app = QApplication.instance()

        if app and hasattr(app, 'shuttingDown') and app.shuttingDown is True:
            # Prevent emitting signals during the app's shutdown
            log.debug(
                '{!r}: Application is shutting down, not emitting'.format(
                    self))
            return

        if len(args) != len(self._sig):
            log.debug(
                '{!r}: does not match signature: {} !'.format(
                    self, *args))
            return

        for receiver in self:
            try:
                if isinstance(receiver, functools.partial) and \
                        asyncio.iscoroutinefunction(receiver.func):
                    await receiver.func(*(receiver.args + args), **kwargs)
                elif isinstance(receiver, functools.partial) and \
                        callable(receiver.func):
                    receiver.func(*(receiver.args + args), **kwargs)
                elif asyncio.iscoroutinefunction(receiver):
                    await receiver(*args, **kwargs)
            except Exception as err:
                log.debug(
                    '{!r}: callback: {cbk}: exception at emission: {e}'.format(
                        self, cbk=receiver, e=str(err)))
                traceback.print_exc()
                continue
            else:
                self._emitCount += 0
                await self.fire()


def loopTime():
    loop = asyncio.get_event_loop()
    if loop:
        return loop.time()


def ensureGenericCallback(future):
    try:
        future.result()
    except Exception:
        traceback.print_exc()


def ensureSafe(coro, **kw):
    loop = kw.pop('loop', asyncio.get_event_loop())
    callback = kw.pop('futcallback', ensureGenericCallback)

    future = asyncio.run_coroutine_threadsafe(
        coro,
        loop
    )
    if callback:
        future.add_done_callback(callback)

    return future


def ensure(coro, **kw):
    """ 'futcallback' should not be used in the coroutine's kwargs """

    from galacteek import log

    app = QApplication.instance()

    callback = kw.pop('futcallback', ensureGenericCallback)

    if app and hasattr(app, 'loop'):
        kw.update(loop=app.loop)

    future = asyncio.ensure_future(coro, **kw)

    if callback:
        future.add_done_callback(callback)

    if app and hasattr(app, 'cmdArgs') and app.cmdArgs.asynciodebug:
        # Save the cost of debug() calls here..
        lTime = loopTime()
        log.debug(f'Ensured new task (loop time: {lTime}): {future!r}')

    return future


def partialEnsureSafe(coro, *args, **kw):
    loop = asyncio.get_event_loop()

    def _pwrapper(coro, *args, **kw):
        asyncio.run_coroutine_threadsafe(
            coro(*args, **kw),
            loop
        )

    return functools.partial(_pwrapper, coro, *args, **kw)


partialEnsure = partialEnsureSafe


def soonish(cbk, *args, **kw):
    """ Soon. Or a bit later .. """
    loop = kw.pop('loop', asyncio.get_event_loop())
    loop.call_soon(functools.partial(cbk, *args, **kw))


def ensureLater(delay: int, coro, *args, **kw):
    loop = asyncio.get_event_loop()
    loop.call_later(delay, ensure, coro(*args, **kw))


class asyncify:
    def __init__(self, wrapped):
        self.wrapped = wrapped
        self.name = wrapped.__name__

    def __get__(self, inst, owner):
        def wrapper(*args, **kw):
            return asyncio.ensure_future(self.wrapped(inst, *args, **kw))
        return wrapper


def asyncifyfn(fn):
    @functools.wraps(fn)
    def ensureFn(*args, **kwargs):
        return asyncio.ensure_future(fn(*args, **kwargs))
    return ensureFn


def callAt(loop, callback, delay, *args, **kw):
    now = loop.time()
    return loop.call_at(now + delay, callback, *args)


def async_enterable(f):
    """

    From aioftp.common

    Decorator. Bring coroutine result up, so it can be used as async context

    ::

        >>> async def foo():
        ...
        ...     ...
        ...     return AsyncContextInstance(...)
        ...
        ... ctx = await foo()
        ... async with ctx:
        ...
        ...     # do

    ::

        >>> @async_enterable
        ... async def foo():
        ...
        ...     ...
        ...     return AsyncContextInstance(...)
        ...
        ... async with foo() as ctx:
        ...
        ...     # do
        ...
        ... ctx = await foo()
        ... async with ctx:
        ...
        ...     # do

    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):

        class AsyncEnterableInstance:

            async def __aenter__(self):
                self.context = await f(*args, **kwargs)
                return await self.context.__aenter__()

            async def __aexit__(self, *args, **kwargs):
                await self.context.__aexit__(*args, **kwargs)

            def __await__(self):
                return f(*args, **kwargs).__await__()

        return AsyncEnterableInstance()

    return wrapper


async def asyncReadFile(path, mode='rb', size=None):
    try:
        async with aiofiles.open(path, mode) as fd:
            if size:
                return await fd.read(size)
            else:
                return await fd.read()
    except BaseException:
        return None


async def asyncReadTextFileChunked(path, mode='rt', chunksize=8192):
    try:
        async with open_async(path, mode) as f:
            async for chunk in f.async_readchunks(chunksize):
                yield chunk
    except BaseException as err:
        print(str(err))


async def asyncWriteFile(path, data, mode='w+b'):
    try:
        async with aiofiles.open(path, mode) as fd:
            await fd.write(data)
    except BaseException:
        return None


async def threadExec(fn, *args, processor=None):
    loop = asyncio.get_event_loop()

    with QThreadExecutor(1) as texec:
        res = await loop.run_in_executor(texec, fn, *args)
        if asyncio.iscoroutinefunction(processor):
            return await processor(res)

        return res


def _all_tasks(loop=None):
    """For compat with py3.5 and py3.6"""
    try:
        return asyncio.all_tasks(loop=loop)
    except AttributeError:
        return {t for t in asyncio.Task.all_tasks(loop=loop) if not t.done()}


async def cancelAllTasks(*, timeout=None, raise_timeout_error=False):
    """
    From sakaio.sakaio.cancel_all_tasks (version 3.0 not on pypi)

    https://github.com/nitely/sakaio
    """

    from galacteek import log

    def _warn_pending():
        running = _all_tasks(loop=loop)
        if running:
            log.debug(
                'There are {tc} pending tasks, first 10: {first}',
                tc=len(running), first=list(running)[:10])

    loop = asyncio.get_event_loop()
    running = _all_tasks(loop=loop)

    for t in running:
        t.cancel()

    for f in asyncio.as_completed(running, timeout=timeout, loop=loop):
        try:
            await f
        except asyncio.CancelledError:
            pass
        except asyncio.TimeoutError:
            _warn_pending()
            if raise_timeout_error:
                raise
        except Exception:
            log.warning('Task Error!', exc_info=True)
            pass

    # Tasks scheduled by clean-ups or
    # by tasks ignoring cancellation
    _warn_pending()


async def asyncRmTree(path: str):
    from galacteek import log

    loop = asyncio.get_event_loop()

    def _rmtree(dirpath):
        shutil.rmtree(dirpath, ignore_errors=True)

    if os.path.isdir(path):
        log.debug(f'asyncRmTree: {path}')

        return await loop.run_in_executor(
            None,
            _rmtree,
            path
        )


def clientSessionWithProxy(proxyUrl: str):
    if proxyUrl and proxyUrl.startswith('socks5://'):
        return aiohttp.ClientSession(
            connector=ProxyConnector.from_url(proxyUrl))
    else:
        return aiohttp.ClientSession()


class ThreadLoop:
    def __init__(self):
        self.loop = asyncio.new_event_loop()

    def start(self):
        threading.Thread(target=self.loop.run_forever).start()

    async def submit(self, awaitable):
        f = asyncio.run_coroutine_threadsafe(awaitable, self.loop)
        f2 = asyncio.wrap_future(f, loop=self.loop)
        return await f2

    def stop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)


class GThrottler:
    """
    Same as asyncio_throttle but uses loop time instead of clock time
    """
    def __init__(self, rate_limit: int, period=1.0, retry_interval=0.01,
                 name='generic-throttler'):
        self.rate_limit = rate_limit
        self.period = period
        self.retry_interval = retry_interval
        self.name = name

        self._running = True

        self._task_logs: Deque[float] = deque()

    def shutdown(self):
        self._running = False

    def debug(self, msg):
        from galacteek import log
        log.debug(f'Throttler {self.name}: {msg}')

    def flush(self):
        nowLt = loopTime()

        while self._task_logs:
            diff = nowLt - self._task_logs[0]
            if diff > self.period:
                # self.debug(f'Flush item: diff {diff} > {self.period}')
                self._task_logs.popleft()
            else:
                break

    async def acquire(self):
        while self._running:
            self.flush()

            if len(self._task_logs) < self.rate_limit:
                # self.debug(f'acquired (log count: {len(self._task_logs)})')
                break

            await asyncio.sleep(self.retry_interval)

        self._task_logs.append(loopTime())

    async def __aenter__(self):
        await self.acquire()

    async def __aexit__(self, exc_type, exc, tb):
        pass


def coroInThread(coro, *args):
    app = QApplication.instance()
    loop = asyncio.new_event_loop()
    return loop.run_until_complete(coro(app, loop, *args))


def threadedCoro(coro, *args):
    """
    Runs a coroutine in a new event loop (using a dedicated thread)
    """

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(coroInThread, coro, *args)
        try:
            return future.result()
        except Exception as err:
            print(str(err))
