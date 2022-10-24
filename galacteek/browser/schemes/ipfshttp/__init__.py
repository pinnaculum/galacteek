from aiohttp.web_exceptions import HTTPNotFound
from aiohttp.web_exceptions import HTTPForbidden

from galacteek.browser.schemes import BaseURLSchemeHandler

from galacteek.ipfs import ipfsOp

from iphttp import IpfsHttpServerError
from iphttp.request import request as iphttpRequest


class IpfsHttpSchemeHandler(BaseURLSchemeHandler):
    @ipfsOp
    async def handleRequest(self, ipfsop, request, uid):
        rUrl = request.requestUrl()
        rMethod = bytes(request.requestMethod()).decode()
        buf = self.getBuffer(request)

        if rMethod != 'GET':
            # Limit to GET requests
            return self.reqDenied(request)

        try:
            data, mimeType = await iphttpRequest(
                ipfsop.client,
                rUrl.toString(),
                buffer=buf,
                method=rMethod
            )

            if mimeType:
                request.reply(mimeType.encode('ascii'), buf)
        except IpfsHttpServerError as herr:
            # Handle HTTP errors from the server
            if herr.http_status == HTTPNotFound.status_code:
                self.urlNotFound(request)
            elif herr.http_status == HTTPForbidden.status_code:
                self.reqDenied(request)
            else:
                self.reqFailed(request)
        except Exception:
            self.reqFailed(request)
