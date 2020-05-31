from galacteek.dweb.cyber import cyberSearch
from galacteek.ipfs import ipfssearch

import asyncio
import itertools


def alternate(s1, s2):
    xs = s1.hits
    ys = s2.hits
    head = itertools.chain.from_iterable(zip(xs, ys))
    return itertools.chain(head, xs[len(ys):], ys[len(xs):])


async def multiSearch(query, page=0,
                      filters=None, sslverify=True):
    """
    Perform a search query on multiple search
    engines (ipfs-search and cyber). This is an
    async generator alternatingly yielding results
    from each engine
    """

    results = await asyncio.gather(
        ipfssearch.getPageResults(query, page,
                                  filters=filters if filters else {},
                                  sslverify=sslverify),
        cyberSearch(query, page=page, perPage=20, sslverify=sslverify)
    )

    if len(results) == 2:
        maxPcount = max(r.pageCount for r in results)
        for res in alternate(results[0], results[1]):
            yield maxPcount, res
