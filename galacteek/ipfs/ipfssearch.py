from urllib.parse import quote
from async_generator import async_generator, yield_

from galacteek import log

import aiohttp

ipfsSearchApiHost = 'api.ipfs-search.com'


class IPFSSearchResults:
    def __init__(self, page, results):
        self.pageCount = results.get('page_count', 0)
        self.resultsCount = results.get('total', 0)
        self.page = page
        self.results = results

    @property
    def hits(self):
        return self.results.get('hits', [])

    def findByHash(self, hashV):
        for hit in self.hits:
            hitHash = hit.get('hash', None)
            if hitHash == hashV:
                return hit


emptyResults = IPFSSearchResults(0, {})


async def searchPage(query, page, filters={}, sslverify=True):

    params = {
        'q': query,
        'page': page
    }

    for fkey, fvalue in filters.items():
        params['q'] += quote(' {fkey}:{fvalue}'.format(
            fkey=fkey, fvalue=fvalue))

    async with aiohttp.ClientSession() as session:
        async with session.get('https://{host}/v1/search'.format(
                host=ipfsSearchApiHost),
                params=params,
                verify_ssl=sslverify) as resp:
            return await resp.json()


async def getPageResults(query, page, filters={}, sslverify=True):
    try:
        results = await searchPage(query, page, filters=filters,
                                   sslverify=sslverify)
        return IPFSSearchResults(page, results)
    except Exception:
        return None


async def getMetadata(cid, sslverify=True):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://{host}/v1/metadata/{cid}'.format(
                    host=ipfsSearchApiHost, cid=cid),
                    verify_ssl=sslverify) as resp:
                return await resp.json()
    except Exception:
        log.debug('Error occured while fetching metadata')
        return None


@async_generator
async def search(query, preloadPages=0, filters={}, sslverify=True):
    page1Results = await getPageResults(query, 0, filters=filters,
                                        sslverify=sslverify)
    if page1Results is None:
        await yield_(emptyResults)
        return

    await yield_(page1Results)
    pageCount = page1Results.pageCount

    if preloadPages > 0:
        pageLast = preloadPages if pageCount >= preloadPages else pageCount
        for page in range(page1Results.page + 1, pageLast + 1):
            results = await getPageResults(query, page, filters=filters,
                                           sslverify=sslverify)
            if results:
                await yield_(results)
