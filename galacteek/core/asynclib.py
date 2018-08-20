
import asyncio
import functools

def asyncify(fn):
    @functools.wraps(fn)
    def ensureFn(*args, **kwargs):
          return asyncio.ensure_future(fn(*args, **kwargs))
    return ensureFn
