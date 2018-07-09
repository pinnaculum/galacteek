
import asyncio
import argparse
import sys
import json
import os

from async_generator import async_generator, yield_

import aiohttp

class IPFSSearchResults:
    def __init__(self, page, results):
        self.pageCount = results.get('page_count', 0)
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

async def searchPage(query, page):
    params = {
            'q': query,
            'page': page
            }

    async with aiohttp.ClientSession() as session:
        async with session.get('https://api.ipfs-search.com/v1/search',
                params=params) as resp:
            return await resp.json()

async def getPageResults(query, page):
    try:
        results = await searchPage(query, page)
        return IPFSSearchResults(page, results)
    except Exception as e:
        return None

@async_generator
async def search(query, preloadPages=0):
    page1Results = await getPageResults(query, 0)
    if page1Results is None:
        await yield_(emptyResults)
        return

    await yield_(page1Results)
    pageCount = page1Results.pageCount

    if preloadPages > 0:
        pageLast = preloadPages if pageCount >= preloadPages else pageCount
        for page in range(page1Results.page+1, pageLast+1):
            results = await getPageResults(query, page)
            if results:
                await yield_(results)
