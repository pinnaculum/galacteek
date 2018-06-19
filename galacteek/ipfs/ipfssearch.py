
import asyncio
import argparse
import sys
import json
import os

from async_generator import async_generator, yield_

import aiohttp

class IPFSSearchResults:
    def __init__(self, page, results):
        self.pageCount = results['page_count']
        self.page = page
        self.results = results

    def hits(self):
        for hit in self.results['hits']:
            yield hit

async def searchPage(query, page):
    params = {
            'q': query,
            'page': page
            }

    async with aiohttp.ClientSession() as session:
        async with session.get('https://api.ipfs-search.com/v1/search',
                params=params) as resp:
            return await resp.json()

async def searchPageResults(query, page):
    try:
        results = await searchPage(query, page)
        return IPFSSearchResults(page, results)
    except:
        return None

@async_generator
async def search(query, maxpages=12):
    if not query:
        return

    for page in range(1, maxpages):
        results = await searchPageResults(query, page)
        if results:
            await yield_(results)
