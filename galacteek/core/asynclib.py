import asyncio
import functools
import aiofiles


def ensure(coro, **kw):
    """ 'futcallback' should not be used in the coroutine's kwargs """
    callback = kw.pop('futcallback', None)
    future = asyncio.ensure_future(coro, **kw)
    if callback:
        future.add_done_callback(callback)
    return future


def soonish(cbk, *args, **kw):
    """ Soon. Or a bit later .. """
    loop = kw.pop('loop', asyncio.get_event_loop())
    loop.call_soon(functools.partial(cbk, *args, **kw))


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


async def asyncReadFile(path, mode='rb'):
    try:
        async with aiofiles.open(path, mode) as fd:
            return await fd.read()
    except BaseException:
        return None
