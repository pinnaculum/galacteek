import aiohttp
import asyncio

from aiohttp.web_exceptions import HTTPOk
from aiohttp.web_exceptions import HTTPNotFound
from aiohttp.web_exceptions import HTTPForbidden

from PyQt5.QtCore import QIODevice

from galacteek import log
from galacteek.browser.schemes import BaseURLSchemeHandler
from galacteek.browser.schemes import SCHEME_IPFS_P_HTTP
from galacteek.browser.schemes import SCHEME_IPFS_P_HTTPS

from galacteek.ipfs import ipfsOp
from galacteek.ipfs.cidhelpers import peerIdBase58


class IpfsHttpServerError(Exception):
    def __init__(self, status_code: int):
        self.http_status = status_code


class IpfsHttpSchemeHandler(BaseURLSchemeHandler):
    """
    Scheme handler for ipfs+http:// and ipfs+https://
    """

    @ipfsOp
    async def handleRequest(self, ipfsop, request, uid):
        rUrl = request.requestUrl()
        hostb36 = rUrl.host()
        port = rUrl.port(80)
        rMethod = bytes(request.requestMethod()).decode()

        if rMethod != 'GET':
            # Limit to GET requests
            return self.reqFailed(request)

        try:
            # base36/base32 => cidv0 (base58) (cached conversion)
            peerId = peerIdBase58(hostb36)
            assert peerId is not None
        except Exception:
            return self.urlInvalid(request)

        if rUrl.scheme() == SCHEME_IPFS_P_HTTP:
            protoName = 'ipfs-http'
            port = rUrl.port(80)
        elif rUrl.scheme() == SCHEME_IPFS_P_HTTPS:
            protoName = 'ipfs-https'
            port = rUrl.port(443)
        else:
            return self.urlInvalid(request)

        # ipfs-http P2P endpoint address
        p2pEndpoint = f'/p2p/{peerId}/x/{protoName}/{port}/1.0'

        try:
            # Tunnel
            async with ipfsop.p2pDialerFromAddr(p2pEndpoint,
                                                allowLoopback=True) as dial:
                if dial.failed:
                    raise Exception(f'Dialing {peerId} failed')

                url = dial.httpUrl(
                    rUrl.path(),
                    query=rUrl.query(),
                    fragment=rUrl.fragment()
                )

                buf = self.getBuffer(request)
                buf.open(QIODevice.WriteOnly)

                async with aiohttp.ClientSession() as sess:
                    async with sess.get(url) as resp:
                        if resp.status != HTTPOk.status_code:
                            raise IpfsHttpServerError(resp.status)

                        ctyper = resp.headers.get('Content-Type', 'text/html')

                        # Write in chunks

                        async for chunk in resp.content.iter_chunked(32768):
                            buf.write(chunk)

                            await asyncio.sleep(0)

                buf.close()

                ctype = ctyper.split(';')[0]
                request.reply(ctype.encode('ascii'), buf)
        except IpfsHttpServerError as herr:
            # Handle HTTP errors from the server
            if herr.http_status == HTTPNotFound.status_code:
                self.urlNotFound(request)
            elif herr.http_status == HTTPForbidden.status_code:
                self.reqDenied(request)
            else:
                self.reqFailed(request)
        except Exception as err:
            log.debug(f'ipfs-http ({p2pEndpoint}) '
                      f'error serving {rUrl.path()}: {err}')

            self.reqFailed(request)
