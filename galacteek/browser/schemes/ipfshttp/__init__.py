import aiohttp

from PyQt5.QtCore import QIODevice

from galacteek import log
from galacteek.browser.schemes import BaseURLSchemeHandler

from galacteek.ipfs import ipfsOp
from galacteek.ipfs.cidhelpers import peerIdBase58


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

        # ipfs-http P2P endpoint address
        # p2pEndpoint = f'/p2p/{peerId}/x/ipfs-http/{port}/1.0'

        if rUrl.scheme() == 'ipfs+http':
            protoName = 'ipfs-http'
            port = rUrl.port(80)
        elif rUrl.scheme() == 'ipfs+https':
            protoName = 'ipfs-https'
            port = rUrl.port(443)

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

                buf = self.requests[uid]['iodev']
                buf.open(QIODevice.WriteOnly)

                async with aiohttp.ClientSession() as sess:
                    async with sess.get(url) as resp:
                        ctyper = resp.headers.get('Content-Type', 'text/html')

                        # Write in chunks

                        async for chunk in resp.content.iter_chunked(32768):
                            buf.write(chunk)

                buf.close()

                ctype = ctyper.split(';')[0]
                request.reply(ctype.encode('ascii'), buf)
        except Exception as err:
            log.debug(f'ipfs-http ({p2pEndpoint}) '
                      f'error serving {rUrl.path()}: {err}')

            self.reqFailed(request)
