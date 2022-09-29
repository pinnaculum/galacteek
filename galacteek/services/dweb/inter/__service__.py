import asyncio
import traceback

from galacteek import log
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
            self.rootPath,
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
        while not self.should_stop:
            try:
                lastSetupRes = await self.interceptor.reconfigure()
            except Exception:
                log.debug(traceback.format_exc())

            await asyncio.sleep(
                60 * 5 if lastSetupRes is False else 60 * 60 * 3
            )


def serviceCreate(dotPath, config, parent: GService):
    return InterceptorService(dotPath=dotPath, config=config)
