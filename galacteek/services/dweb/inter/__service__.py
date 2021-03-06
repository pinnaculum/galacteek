import asyncio

from galacteek import cached_property
from galacteek.services import GService
from galacteek.browser.interceptor import IPFSRequestInterceptor

from . import InterceptorMessageTypes


class InterceptorService(GService):
    name = 'interceptor'
    ident = 'g/dweb/inter'

    @cached_property
    def queue(self):
        return asyncio.Queue()

    @cached_property
    def interceptor(self):
        return IPFSRequestInterceptor(
            self.serviceConfig,
            self.queue,
            parent=self.app
        )

    async def on_start(self):
        await super().on_start()

        # Notify the webprofiles
        await self.ldPublish({
            'type': InterceptorMessageTypes.Ready,
            'interceptor': self.interceptor
        })

    @GService.task
    async def processQueue(self):
        return

        while True:
            url, info = await self.queue.get()

            await asyncio.sleep(0.2)


def serviceCreate(dotPath, config, parent: GService):
    return InterceptorService(dotPath=dotPath, config=config)
