import re

from galacteek.core.ps import KeyListener
from galacteek import AsyncSignal
from galacteek.core.ps import makeKeyService


class GraphActivityListener(KeyListener):
    psListenKeys = [
        makeKeyService('ld', 'pronto')
    ]

    urisWatchList = []

    def __init__(self, watch: list = []):
        super().__init__()

        if isinstance(watch, list):
            self.urisWatchList += watch

        self.asNeedUpdate = AsyncSignal(str)

    async def event_g_services_ld_pronto(self, key, message):
        deliver = False
        event = message['event']

        if event['type'] == 'GraphUpdateEvent':
            graphUri = event.get('graphUri')
            if not graphUri:
                return

            for uriReg in self.urisWatchList:
                if re.search(uriReg, graphUri):
                    deliver = True
                    break

            if deliver is True:
                await self.asNeedUpdate.emit(graphUri)
