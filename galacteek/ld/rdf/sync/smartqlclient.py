import zlib
import async_timeout
import aiohttp

from galacteek import log
from galacteek.ld.rdf import BaseGraph
from galacteek.ld.sparql.aioclient import Sparkie


class SmartQLClient:
    def __init__(self, dialCtx, auth: aiohttp.BasicAuth = None):
        self.dial = dialCtx

        self.auth = auth if auth else aiohttp.BasicAuth('smartql', 'default')
        self.spql = Sparkie(self.dial.httpUrl('/sparql'), auth=self.auth)

    async def resource(self, iri, context=None, timeout=60):
        graph = BaseGraph()
        url = self.dial.httpUrl(f'/resource/{iri}/graph')

        headers = {
            'Accept': 'application/x-turtle'
        }

        params = {
            'fmt': 'ttl',
            'context': context
        }

        try:
            with async_timeout.timeout(timeout):
                async with aiohttp.ClientSession(headers=headers,
                                                 auth=self.auth) as session:
                    async with session.get(url, params=params) as resp:
                        data = await resp.read()
                        assert data is not None

                        ctype = resp.headers.get('Content-Type')

                        if ctype == 'application/gzip':
                            gdata = zlib.decompress(data).decode()
                        else:
                            gdata = data.decode()

                        graph.parse(data=gdata, format=params['fmt'])
        except Exception as err:
            log.debug(f'resource graph pull error for {iri}: {err}')
        else:
            log.debug(f'resource graph pull for {iri}: success')
            return gdata
