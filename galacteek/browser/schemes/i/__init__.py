import aiohttp

from rdflib import URIRef
from rdflib.plugins.sparql import prepareQuery

from galacteek import services
from galacteek.ld import uriTermExtract
from galacteek.ld.sparql import uri_objtype


from galacteek import cached_property
from galacteek.ipfs import ipfsOp

from galacteek.browser.schemes import NativeIPFSSchemeHandler


class ISchemeHandler(NativeIPFSSchemeHandler):
    @property
    def iService(self):
        return services.getByDotName('dweb.schemes.i')

    @property
    def pronto(self):
        return services.getByDotName('ld.pronto')

    @cached_property
    def connector(self):
        return aiohttp.UnixConnector(
            path=self.iService.socketPath
        )

    @ipfsOp
    async def handleRequestViaIService(self, ipfsop, request, uid):
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

    @ipfsOp
    async def handleRequest(self, ipfsop, request, uid):
        rUrl = request.requestUrl()
        path = rUrl.path()

        ipid = await ipfsop.ipid()
        if not ipid:
            return self.reqFailed(request)

        path = rUrl.path()
        rscUri = f'i:{path}'

        try:
            results = list(await self.pronto.gQuery(
                uri_objtype(rscUri).get_text()))
            otype = uriTermExtract(results[0]['type'])
        except Exception:
            return self.reqFailed(request)

        # TODO: check object type, fixed for test
        tmpl = self.app.jinjaEnv.get_template(
            f'ld/components/{otype}/render.jinja2'
        )

        if tmpl:
            content = await tmpl.render_async(
                graph=self.pronto.graphG,
                prepareQuery=prepareQuery,
                ipid=ipid,
                rscUri=rscUri,
                URIRef=URIRef
            )
            self.serveContent(
                uid,
                request,
                'text/html',
                content.encode()
            )
        else:
            self.reqFailed(request)
