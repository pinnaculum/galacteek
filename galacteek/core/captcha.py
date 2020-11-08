import asyncio
import random
import tempfile
import functools

from claptcha import Claptcha
from PIL import Image

from galacteek.core import qrcWriteToTemp
from galacteek.ipfs import ipfsOpFn


@functools.lru_cache(maxsize=1)
def ttfFont():
    return qrcWriteToTemp(':/share/static/fonts/DejaVuSans.ttf')


async def randomCaptcha(length=8, noise=0.3):
    loop = asyncio.get_event_loop()

    def _gen():
        try:
            fp = tempfile.mkstemp(prefix='captcha')[1]
            r = random.Random()
            secret = ''

            tmpFont = ttfFont()

            for x in range(length):
                secret += str(r.randint(0, 9))

            secret = 'abcd'
            c = Claptcha(secret, tmpFont,
                         resample=Image.BICUBIC, noise=noise)
            c.write(fp)
            return secret, fp
        except Exception:
            return None, None

    return await loop.run_in_executor(None, _gen)


@ipfsOpFn
async def randomCaptchaIpfs(ipfsop, length=8, noise=0.3):
    secret, path = await randomCaptcha(length=length, noise=noise)

    if path:
        entry = await ipfsop.addPath(path, wrap=False)
        return secret, entry['Hash']
    else:
        return None, None
