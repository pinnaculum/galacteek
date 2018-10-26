import asyncio
import aiohttp

from distutils.version import StrictVersion

from galacteek import __version__


async def getLatestVersion(pkgname='galacteek'):
    url = 'https://pypi.org/pypi/{0}/json'.format(pkgname)

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            return StrictVersion(data['info']['version'])


async def newReleaseAvailable():
    try:
        latestV = await getLatestVersion()
        currentV = StrictVersion(__version__)
        return latestV > currentV
    except asyncio.TimeoutError:
        return False
    except BaseException:
        return False
