import asyncio
import re

from collections import deque
from datetime import timedelta
from typing import Union

from galacteek import AsyncSignal
from galacteek import ensure
from galacteek import services

from galacteek.config import DictConfig

from galacteek.core import utcDatetime

from galacteek.core.ps import KeyListener
from galacteek.core.ps import makeKeyService

from galacteek.ld.rdf import BaseGraph
from galacteek.ld.rdf import GraphUpdateEvent


class GraphActivityListener(KeyListener):
    """
    Pubsub activity listener for pronto graphs
    """

    psListenKeys = [
        makeKeyService('ld', 'pronto')
    ]

    reading: bool = False

    def __init__(self, watch: Union[list, str] = None,
                 minChangesInterval: int = 2):
        super().__init__()

        self.urisWatchList = []
        self.sbuffers = {}
        self.evflushd = {}
        self.eventsq = asyncio.Queue()

        if isinstance(watch, list):
            self.urisWatchList += [uri for uri in watch if
                                   isinstance(uri, str)]
        elif isinstance(watch, str):
            self.urisWatchList.append(watch)

        self.graphChanged = AsyncSignal(str,
                                        minInterval=minChangesInterval)

        self.subjectsChanged = AsyncSignal(str, list)

        self.graphGotMerged = AsyncSignal(str, BaseGraph)

        ensure(self.readQueue())

    @property
    def pronto(self):
        return services.getByDotName('ld.pronto')

    @property
    def configDef(self):
        return self.config()

    def config(self, graphUri: str = 'default') -> DictConfig:
        return self.pronto.serviceConfig.graphWatcher.get(graphUri)

    async def readQueue(self) -> None:
        try:
            self.reading = True

            while self.reading:
                graphUri, subjects = await self.eventsq.get()

                if not graphUri or not subjects:
                    await asyncio.sleep(0)
                    continue

                await self.subjectsChanged.emit(graphUri, subjects)

                await asyncio.sleep(self.config().eventReadInterval)
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    async def flush(self, graphUri: str, subjects: deque) -> None:
        lastf = self.evflushd.get(graphUri, None)

        cond = not lastf or (lastf and (utcDatetime() - lastf) > timedelta(
            seconds=self.configDef.get('flushSubjectsInactiveSecs', 60)
        ))

        if len(subjects) > self.configDef.minSubjectsPerFlush and cond:
            await self.eventsq.put((graphUri, list(subjects)))

            # Reset
            subjects.clear()

            self.evflushd[graphUri] = utcDatetime()

    async def event_g_services_ld_pronto(self,
                                         key,
                                         message: Union[GraphUpdateEvent,
                                                        dict]) -> None:
        if isinstance(message, GraphUpdateEvent):
            for uriReg in self.urisWatchList:
                if re.search(uriReg, message.graphUri):
                    # Emit graphGotMerged
                    await self.graphGotMerged.emit(
                        message.graphUri,
                        message.srcGraph
                    )
            return

        # LD event
        event = message['event']

        if event['type'] == 'GraphUpdateEvent':
            graphUri = event.get('graphUri')
            subjects = event.get('subjectsUris')

            if not graphUri:
                return

            for uriReg in self.urisWatchList:
                if re.search(uriReg, graphUri):
                    await self.graphChanged.emit(graphUri)

                    if isinstance(subjects, list):
                        esubs = self.sbuffers.setdefault(
                            graphUri,
                            deque([],
                                  maxlen=self.config().maxEventSubjects)
                        )
                        esubs += subjects

                        await self.flush(graphUri, esubs)

                    break
