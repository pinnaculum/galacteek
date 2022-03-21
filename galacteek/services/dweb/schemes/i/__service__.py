import secrets
from rdflib import URIRef
from rdflib.plugins.sparql import prepareQuery

from aiohttp import web

from galacteek import services
from galacteek.ipfs import ipfsOp
from galacteek.core import uid4
from galacteek.ld import uriTermExtract
from galacteek.ld.sparql import uri_objtype


class RootView(web.View):
    @property
    def stores(self):
        return services.getByDotName('ld.pronto')

    @ipfsOp
    async def get(self, ipfsop):
        curProfile = ipfsop.ctx.currentProfile
        ipid = await curProfile.userInfo.ipIdentifier()

        app = self.request.app.gApp
        minfo = self.request.match_info
        path = minfo.get('obj', None)

        rscUri = f'i:/{path}'

        try:
            results = list(await self.stores.gQuery(
                uri_objtype(rscUri).get_text()))
            otype = uriTermExtract(results[0]['type'])
        except Exception:
            return web.Response(
                text=f'Unknown object: {rscUri}'
            )

        # TODO: check object type, fixed for test
        tmpl = app.jinjaEnv.get_template(
            f'ld/components/{otype}/render.jinja2'
        )

        if tmpl:
            return web.Response(
                text=await tmpl.render_async(
                    graph=self.stores.graphG,
                    prepareQuery=prepareQuery,
                    ipid=ipid,
                    rscUri=rscUri,
                    URIRef=URIRef
                ))


class GraphsView(web.View):
    @property
    def stores(self):
        return services.getByDotName('ld.pronto')

    async def get(self):
        minfo = self.request.match_info

        gname = minfo.get('g', 'g')
        fmt = minfo.get('fmt', 'xml')

        graph = self.stores._graphs.get(gname, None)

        if fmt == 'xml':
            data = await graph.xmlize()
        elif fmt == 'ttl':
            data = await graph.ttlize()
        return web.Response(
            content_type='application/rdf+xml',
            text=data.decode()
        )


class IService(services.GService):
    name = 'i'

    @property
    def prontoService(self):
        return services.getByDotName('ld.pronto')

    def on_init(self):
        self.socketPath = self.rootPath.joinpath('i.sock')

    def iriGenObject(self, oclass):
        s = secrets.token_hex(16)
        return f'i:/{self.prontoService.chainEnv}/rsc/{oclass}/{s}-{uid4()}'

    async def startWebApp(self):
        self.webapp = self.createApp()

        self.webtask = await self.app.scheduler.spawn(
            web._run_app(self.webapp, path=str(self.socketPath))
        )

    def createApp(self):
        app = web.Application()
        app.gApp = self.app

        app.router.add_routes([
            # web.view('/graphs/{g:.*}/{fmt:.*}', GraphsView),
            web.view('/{obj:.*}', RootView)
        ])

        return app

    async def on_stop(self):
        pass


def serviceCreate(dotPath, config, parent: services.GService):
    return IService(dotPath=dotPath, config=config)
