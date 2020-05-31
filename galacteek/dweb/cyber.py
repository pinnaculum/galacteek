from galacteek import log
from galacteek.ipfs import ipfsOpFn

import aiohttp


class CyberSearchResults:
    def __init__(self, pageCount, page, results):
        self.pageCount = pageCount
        self.page = page
        self.results = results

    @property
    def hits(self):
        return [{
            'hit': hit,
            'pageCount': self.pageCount,
            'page': self.page,
            'engine': 'cyber'
        } for hit in self.results['hits']]

    @property
    def hitsCount(self):
        return len(self.hits)


@ipfsOpFn
async def cyberSearch(ipfsop, query: str, page=0, perPage=10, sslverify=True):
    entry = await ipfsop.hashComputeString(query, cidversion=0)

    params = {
        'cid': '"{qcid}"'.format(qcid=entry['Hash']),
        'page': page,
        'perPage': perPage
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://{host}/api/search'.format(
                    host='titan.cybernode.ai'),
                    params=params,
                    verify_ssl=sslverify) as resp:
                resp = await resp.json()
                result = resp['result']
                total = int(result['total'])
                cids = result['cids']
                pageCount = int(total / perPage)
    except Exception as err:
        log.debug(str(err))
        return CyberSearchResults(
            0,
            page,
            {
                'total': 0,
                'page_size': perPage,
                'page_count': 0,
                'hits': []
            }
        )
    else:
        _sorted = sorted(
            cids,
            reverse=True,
            key=lambda it: it['rank']
        )

        def _format(r):
            return {
                'hash': r['cid'],
                'title': r['cid'],
                'score': r['rank']
            }

        return CyberSearchResults(
            pageCount,
            page,
            {
                'total': total,
                'page_size': perPage,
                'page_count': pageCount,
                'hits': [_format(r) for r in _sorted]
            }
        )
