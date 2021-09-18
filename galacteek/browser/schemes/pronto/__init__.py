import pydotplus
from io import StringIO
from io import BytesIO
from rdflib.tools.rdf2dot import rdf2dot

from galacteek import log
from galacteek.ipfs import ipfsOp

from galacteek.browser.schemes import BaseURLSchemeHandler

from galacteek.services import getByDotName

from PyQt5.QtCore import QUrlQuery


class ProntoGraphsSchemeHandler(BaseURLSchemeHandler):
    """
    Renders pronto graphs in the browser (in ttl, xml or via pydot)

    prontog:/urn:ipg:g:c0?format=xml
    prontog:/urn:ipg:g:c0?format=dot
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
            # Graph's URI is the first component of the path
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
            elif fmt in ['dot', 'image']:
                # Render with pydotplus

                def dotRender():
                    png = BytesIO()
                    stream = StringIO()
                    rdf2dot(graph, stream)
                    dg = pydotplus.graph_from_dot_data(stream.getvalue())

                    dg.set_size('1024,768!')

                    dg.write(png, format='png')
                    png.seek(0, 0)

                    return png

                png = await self.app.rexec(dotRender)
                if png:
                    return self.serveContent(
                        request.reqUid,
                        request,
                        'image/png',
                        png.getvalue()
                    )
            else:
                return self.serveContent(
                    request.reqUid,
                    request,
                    'application/xml',
                    await graph.xmlize()
                )
        except Exception as err:
            log.debug(f'{path}: error rendering graph: {err}')
            return self.reqFailed(request)
