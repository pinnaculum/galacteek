from galacteek import log
from galacteek.did.ipid.services import IPService
from galacteek.ipfs.p2pservices import gemini as p2pgemini


class GeminiCapsuleService(IPService):
    forTypes = [IPService.SRV_TYPE_GEMINI_CAPSULE]
    endpointName = 'GeminiIpfsCapsuleServiceEndpoint'

    async def serviceStart(self):
        try:
            cfg = p2pgemini.GeminiServiceConfig(
                capsuleName=self.endpoint.get('capsuleName', 'default'),
                servePath=self.endpoint['capsuleIpfsPath']
            )

            srv = p2pgemini.P2PGeminiService(config=cfg)
            await self.p2pServiceRegister(srv)
        except Exception as err:
            log.debug(
                f'{self.id}: Could not start gemini capsule service: {err}')

    def __str__(self):
        return 'Gemini IPFS capsule'
