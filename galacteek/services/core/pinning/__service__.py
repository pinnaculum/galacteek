import asyncio

from galacteek import log

from galacteek.services import GService

from galacteek.config.cmods import pinning as cfgpinning
from galacteek.ipfs.pinning import remote

from .events import RPSEvents


RPS_S_QUEUED = 'Queued'
RPS_S_PINNED = 'Pinned'
RPS_S_PINNING = 'Pinning'
RPS_S_FAILED = 'Failed'


class RemotePinServicesMaster(GService):
    name = 'remotepinning'

    @property
    def observeEvery(self):
        self.serviceConfig.rpsObserver.statEvery

    async def declareSystem(self):
        self.manager = remote.RemotePinServicesManager()

    @GService.task
    async def remoteObserverTask(self):
        while not self.should_stop:
            await asyncio.sleep(self.observeEvery)

            await self.rpsObserve()

    async def rpsObserve(self):
        try:
            sCount = cfgpinning.rpsCount()
            if sCount == 0:
                log.debug('RPS observer: no services')
                return

            stat = await self.manager.remoteServicesStat()

            if not stat:
                log.debug('RPS observer: stat empty')
                return

            for service in stat:
                cfg = cfgpinning.rpsConfigGetByServiceName(
                    service['Service']
                )

                if not cfg:
                    log.debug(
                        f'RPS observer: no config for {service}')
                    continue

                pins = await self.manager.pinsForRps(
                    service['Service']
                )

                service['Items'] = pins if pins else []
                for item in pins:
                    status = item.get('Status')

                    if status == RPS_S_PINNING.lower():
                        await self.ldPublish({
                            'type': RPSEvents.RPSPinningHappening,
                            'Name': item.get('Name'),
                            'Cid': item.get('Cid')
                        }, contextName='services/RPSSummaryMessage')

                # Push it as LD
                await self.ldPublish({
                    'type': RPSEvents.ServiceStatusSummary,
                    'serviceStatus': service,
                }, contextName='services/RPSSummaryMessage')

        except Exception as err:
            log.debug(f'Observer error: {err}')


def serviceCreate(dotPath, config, parent: GService):
    return RemotePinServicesMaster(dotPath=dotPath, config=config)
