import aiohttp

from galacteek import cached_property
from galacteek.ipfs import ipfsOp

from galacteek.browser.schemes import NativeIPFSSchemeHandler

from galacteek.services import getByDotName


class ISchemeHandler(NativeIPFSSchemeHandler):
    @property
    def iService(self):
        return getByDotName('dweb.schemes.i')

    @cached_property
    def connector(self):
        return aiohttp.UnixConnector(
            path=self.iService.socketPath
        )

    @ipfsOp
    async def handleRequest(self, ipfsop, request, uid):
        rUrl = request.requestUrl()
        rMethod = bytes(request.requestMethod()).decode()
        path = rUrl.path()

        try:
            async with aiohttp.request(rMethod,
                                       f'http://localhost{path}',
                                       connector=self.connector) as resp:

                assert resp.status == 200
                content = await resp.text()

                self.serveContent(
                    uid,
                    request,
                    'text/html',
                    content.encode()
                )
        except Exception as err:
            print(str(err))
            self.reqFailed(request)
