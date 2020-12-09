from galacteek import log
from galacteek.ipfs import ipfsOp
from galacteek.did.ipid import IPService
from galacteek.ipfs.p2pservices.rendezvous import PSRendezVousService
from galacteek.ipfs.p2pservices import p2pEndpointAddrExplode


class VideoCallService(IPService):
    forTypes = [IPService.SRV_TYPE_VIDEOCALL]
    endpointName = 'DwebVideoCallServiceEndpoint'

    async def p2pEndpointAddr(self):
        try:
            q = await self.expandEndpointLdWizard()
            return q.gu(
                'DwebVideoCallServiceEndpoint',
                'p2pEndpoint'
            )
        except Exception as err:
            log.debug(err)

    @ipfsOp
    async def serviceStart(self, ipfsop):
        """
        Start the P2P service for this videocall DID service
        """

        # Look up
        exService = self.ipid.p2pServices.get(self.srvPath)
        if exService:
            log.debug(f'P2P-service already running: {self.srvPath}')
            return False

        try:
            eaddr = await self.p2pEndpointAddr()
            exploded = p2pEndpointAddrExplode(eaddr)
            if not exploded:
                raise Exception('Could not parse endpoint')

            peerId, protoFull, pVersion = exploded

            p2pService = PSRendezVousService(protocolName=protoFull)
            log.debug(f'P2P-service {self.srvPath}: starting')

            await p2pService.start()

            self.ipid.p2pServices[self.srvPath] = p2pService

            return True
        except Exception as err:
            log.debug(err)
            return False

    def __str__(self):
        return 'Video call service'
