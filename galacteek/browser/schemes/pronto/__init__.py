from galacteek.ipfs import ipfsOp

from galacteek.browser.schemes import BaseURLSchemeHandler

from galacteek.services import getByDotName

from PyQt5.QtCore import QUrlQuery


class ProntoGraphsSchemeHandler(BaseURLSchemeHandler):
    """
    Renders pronto graphs in the browser (in ttl or xml)

    prontog:/urn:ipg:g:c0?format=xml
    prontog:/urn:ipg:g:h0
    """
    @property
    def prontoService(self):
        return getByDotName('ld.pronto.graphs')

    @ipfsOp
    async def handleRequest(self, ipfsop, request, uid):
        rUrl = request.requestUrl()
        path = rUrl.path()
        q = QUrlQuery(rUrl.query())
        fmt = q.queryItemValue('format')

        comps = path.lstrip('/').split('/')

        try:
            graphUri = comps.pop(0)
            graph = self.prontoService.graphByUri(graphUri)

            assert graph is not None

            if not fmt or fmt in ['ttl', 'turtle']:
                return self.serveContent(
                    request.reqUid,
                    request,
                    'text/plain',
                    await graph.ttlize()
                )
            else:
                return self.serveContent(
                    request.reqUid,
                    request,
                    'application/xml',
                    await graph.xmlize()
                )
        except Exception:
            return self.reqFailed(request)
