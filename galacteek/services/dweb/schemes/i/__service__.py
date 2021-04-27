from aiohttp import web

from galacteek import services


class RootView(web.View):
    @property
    def stores(self):
        return services.getByDotName('ld.rdf.stores')

    async def get(self):
        app = self.request.app.gApp
        minfo = self.request.match_info
        path = minfo.get('obj', None)

        # TODO: check object type, fixed for test
        t = app.jinjaEnv.get_template(
            'ld/components/Article/render.jinja2'
        )

        return web.Response(
            text=await t.render_async(
                graph=self.stores.graphG,
                rscUri=f'i:/{path}'
            ))


class GraphsView(web.View):
    @property
    def stores(self):
        return services.getByDotName('ld.rdf.stores')

    async def get(self):
        minfo = self.request.match_info

        gname = minfo.get('g', 'g')
        # fmt = minfo.get('fmt', 'xml')

        graph = self.stores._graphs.get(gname, None)

        if graph:
            data = await graph.xmlize()
            return web.Response(
                content_type='application/rdf+xml',
                text=data.decode()
            )


class IService(services.GService):
    name = 'i'

    def on_init(self):
        self.socketPath = self.rootPath.joinpath('i.sock')

    async def on_start(self):
        await super().on_start()

        self.webapp = self.createApp()

        self.webtask = await self.app.scheduler.spawn(
            web._run_app(self.webapp, path=str(self.socketPath))
        )

    def createApp(self):
        app = web.Application()
        app.gApp = self.app

        app.router.add_routes([
            web.view('/graphs/{g:.*}/{fmt:.*}', GraphsView),
            web.view('/{obj:.*}', RootView)
        ])

        return app

    async def on_stop(self):
        pass


def serviceCreate(dotPath, config, parent: services.GService):
    return IService(dotPath=dotPath, config=config)
