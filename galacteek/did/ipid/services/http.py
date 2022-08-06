from galacteek import log
from galacteek.did.ipid.services import IPService
from galacteek.ipfs.p2pservices import httpforward as p2phttpforward


class HttpForwardService(IPService):
    forTypes = [IPService.SRV_TYPE_HTTP_SERVICE,
                IPService.SRV_TYPE_HTTP_FORWARD_SERVICE]
    endpointName = 'HttpForwardServiceEndpoint'

    async def serviceStart(self):
        try:
            await self.p2pServiceRegister(p2phttpforward.P2PHttpForwardService(
                config=p2phttpforward.HttpForwardServiceConfig(
                    advertisePort=self.endpoint.get('httpAdvertisePort'),
                    targetMultiAddr=self.endpoint.get('targetMultiAddr')
                )
            ))
        except Exception as err:
            log.info(
                f'{self.id}: Could not start http forwarding service: {err}')

    def __str__(self):
        return 'HTTP forwarding service'
