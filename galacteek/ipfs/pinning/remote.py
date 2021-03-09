from galacteek.ipfs import ipfsOp

from galacteek import log

from galacteek.core import runningApp
from galacteek.core.ps import KeyListener

from galacteek.config.cmods import pinning as cfgpinning


class RemotePinServicesManager(KeyListener):
    async def event_g_services_app(self, key, message):
        event = message['event']

        reactTo = [
            'IpfsOperatorChange',
            'RPSAdded'
        ]

        if event['type'] in reactTo:
            # IPFS connection change. Scan remote pin services

            log.debug('Performing RPS scan')
            await self.remoteServicesScan()

    @ipfsOp
    async def remoteServicesStat(self, ipfsop):
        try:
            listing = await ipfsop.waitFor(
                ipfsop.pinRemoteServiceList(stat=True),
                timeout=30
            )
        except Exception as err:
            log.debug(str(err))
        else:
            return listing

    @ipfsOp
    async def pinsForRps(self, ipfsop, serviceName: str):
        """
        Returns the list of objects managed by the remote
        pinning service with this service name
        """
        try:
            listing = await ipfsop.waitFor(
                ipfsop.pinRemoteList(
                    serviceName,
                    status=[
                        'pinned',
                        'queued',
                        'failed',
                        'pinning'
                    ]
                ),
                timeout=90
            )
        except Exception as err:
            log.debug(str(err))
        else:
            return listing

    @ipfsOp
    async def remoteServicesScan(self, ipfsop):
        """
        Scan remote pinning services and sync them to the config
        """

        app = runningApp()

        nodeId = await ipfsop.nodeId()

        listing = await ipfsop.pinRemoteServiceList()

        if not nodeId or not listing:
            return

        changed = False
        for rService in listing:
            if cfgpinning.rpsConfigRegister(rService, nodeId):
                changed = True

        if changed:
            await app.s.ldPublish({
                'type': 'RPSConfigChanged'
            })


__all__ = ['RemotePinServicesManager']
