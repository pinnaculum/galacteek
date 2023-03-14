import hashlib
from typing import Union
from pathlib import Path
from yarl import URL

from aiohttp.web_exceptions import HTTPOk

import asyncio
import async_timeout  # noqa
import aiohttp

from galacteek.core import runningApp
from galacteek.core.tmpf import TmpFile
from galacteek.ipfs import megabytes

from galacteek.ipfs.cidhelpers import IPFSPath


async def httpFetch(u,
                    dst: Path = None,
                    timeout=60,
                    chunkSize=8192,
                    maxSize=0,
                    impatient=False,
                    callback=None,
                    firstChunkTimeout=8):
    from galacteek import log

    h = hashlib.sha512()
    url = u if isinstance(u, URL) else URL(u)

    try:
        app = runningApp()
        size = 0

        with TmpFile(mode='w+b', delete=False,
                     suffix=url.name) as file:
            async with aiohttp.ClientSession() as sess:
                async with sess.get(str(url),
                                    verify_ssl=app.sslverify) as resp:
                    if resp.status != HTTPOk.status_code:
                        raise Exception(
                            f'httpFetch: {url}: '
                            f'Invalid reply code: {resp.status}'
                        )

                    contentSize = int(resp.headers.get('Content-Length', 0))

                    if impatient is True:
                        # impatient mode (used when fetching objects
                        # from ipfs http gateways to discard unresponsive gws)

                        firstc = await asyncio.wait_for(
                            resp.content.read(chunkSize),
                            firstChunkTimeout
                        )

                        if not firstc:
                            raise Exception(
                                "Enough is enough: "
                                f"(waited {firstChunkTimeout} secs "
                                "for first crumbs)"
                            )

                        file.write(firstc)
                        h.update(firstc)

                    async for chunk in resp.content.iter_chunked(
                            chunkSize):
                        file.write(chunk)
                        h.update(chunk)

                        size += len(chunk)

                        if size > 0 and contentSize > 0 and callable(callback):
                            callback(size, contentSize)

                        if maxSize > 0 and size > maxSize:
                            raise Exception(
                                f'{url}: capsule size exceeds maxsize')

            file.seek(0, 0)

        return Path(file.name), h.hexdigest()
    except Exception as err:
        log.warning(f'httpFetch ({url}): fetch error: {err}')
        return None, None


async def httpFetchTo(u,
                      dst: Path):
    from . import asyncWriteFile

    url = u if isinstance(u, URL) else URL(u)

    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(str(url)) as resp:
                if resp.status != HTTPOk.status_code:
                    raise Exception(
                        f'httpFetchTo: {url}: '
                        f'Invalid reply code: {resp.status}'
                    )

                await asyncWriteFile(
                    str(dst),
                    await resp.read(),
                    'wb'
                )

        return True
    except Exception:
        return False


async def assetFetch(u: Union[URL, str], **kw):
    from galacteek import log
    from galacteek.ipfs.fetch import fetchWithDedicatedGateway

    location = None
    url = u if isinstance(u, URL) else URL(u)

    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(str(url),
                                allow_redirects=False) as resp:
                location = resp.headers.get('Location')

        aPath = IPFSPath(location)

        if aPath.valid:
            # Pull from gateway

            return await fetchWithDedicatedGateway(
                aPath,
                maxSize=megabytes(8)
            )
        else:
            return await httpFetch(url, **kw)
    except Exception as err:
        log.warning(f'assetFetch ({url}): fetch error: {err}')
        return None, None
