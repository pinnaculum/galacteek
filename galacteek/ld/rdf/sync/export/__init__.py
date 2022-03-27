import zlib
import aiohttp

from galacteek import log
from galacteek.ipfs import ipfsOp
from galacteek.services import GService

from ..cfg import GraphExportSyncConfig


class GraphExportSynchronizer:
    def __init__(self, config=None):
        self.config = config if config else GraphExportSyncConfig()

    @ipfsOp
    async def syncFromRemote(self, ipfsop,
                             peerId: str,
                             iri: str, p2pEndpoint: str,
                             graphDescr=None,
                             p2pLibrarianId=None):
        async with ipfsop.p2pDialerFromAddr(p2pEndpoint) as dial:
            if dial.failed:
                return False

            return await self.syncFromExport(ipfsop, iri, dial,
                                             graphDescr=graphDescr)

    async def syncFromExport(self, ipfsop, iri, dial, graphDescr=None):
        rdfService = GService.byDotName.get('ld.pronto')
        graph = rdfService.graphByUri(iri)

        if graph is None:
            return

        url = dial.httpUrl('/export')
        params = {
            'fmt': self.config.format,
            'compression': self.config.compression
        }

        creds = None
        if graphDescr:
            creds = graphDescr.get('smartqlCredentials')

        if creds:
            auth = aiohttp.BasicAuth(
                creds.get('user', 'smartql'),
                creds.get('password', '')
            )
        else:
            auth = aiohttp.BasicAuth('smartql', 'password')

        try:
            async with aiohttp.ClientSession(auth=auth) as session:
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
            log.debug(f'Graph export sync error for {iri}: {err}')
