from PyQt5.QtCore import QVariant

from galacteek.services import GService
from galacteek.dweb.channels import GServiceQtApi

from galacteek.ipfs.pubsub.srvs.ipid import IPIDPassportPubsubService

from galacteek.dweb.channels import pyqtSlot

from galacteek.core.ps import keyIpidServExposure


class PairingAPI(GServiceQtApi):
    @pyqtSlot(result=QVariant)
    def byDid(self):
        return QVariant(self.service._pairing)


class ProntoPairingService(GService):
    @property
    def prontoService(self):
        return GService.byDotName.get('ld.pronto')

    def on_init(self):
        self.psListen(keyIpidServExposure)
        self.qtApi = PairingAPI(self)
        self._pairing = {}

    async def event_g_ipid_services_exposure(self, key, msg):
        sender, eMsg = msg

        self._pairing[eMsg.did] = {
            'name': eMsg.did,
            'pubsubTopic': eMsg.pubsubTopic
        }
        print(self._pairing)
        return

        found = self.app.ipfsCtx.pubsub.byTopic(eMsg.pubsubTopic)
        if found:
            return

        psService = IPIDPassportPubsubService(
            self.app.ipfsCtx,
            scheduler=self.app.scheduler,
            filterSelfMessages=True,
            topic=eMsg.pubsubTopic
        )
        await psService.startListening()
        print('listening :)', eMsg.pubsubTopic)

    async def on_start(self):
        await super().on_start()


def serviceCreate(dotPath, config, parent: GService):
    return ProntoPairingService(dotPath=dotPath, config=config)
