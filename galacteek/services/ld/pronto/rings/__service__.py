import asyncio
import aiorwlock
from PyQt5.QtCore import QVariant

from galacteek.services import GService
from galacteek.dweb.channels import GServiceQtApi

from galacteek.dweb.channels import pyqtSlot

from galacteek.core.ps import keyIpidServExposure
from galacteek.core.asynclib import loopTime


class PairingAPI(GServiceQtApi):
    @pyqtSlot(result=QVariant)
    def byDid(self):
        return QVariant(self.service._pairing.copy())


class ProntoPairingService(GService):
    @property
    def prontoService(self):
        return GService.byDotName.get('ld.pronto')

    def on_init(self):
        self.psListen(keyIpidServExposure)
        self.qtApi = PairingAPI(self)
        self._pairing = {}
        self._lock = aiorwlock.RWLock(loop=self.app.loop)

    async def event_g_ipid_services_exposure(self, key, msg):
        sender, eMsg = msg

        if sender == self.app.ipfsCtx.node.id:
            return

        async with self._lock.writer_lock:
            self._pairing[eMsg.did] = {
                'name': eMsg.did,
                'pubsubTopic': eMsg.pubsubTopic,
                'ltLast': loopTime()
            }

    @GService.task
    async def cleanup(self):
        while not self.should_stop:
            async with self._lock.reader_lock:
                for did in list(self._pairing.keys()):
                    data = self._pairing[did]

                    if loopTime() - data['ltLast'] > 60:
                        del self._pairing[did]

            await asyncio.sleep(60)

    async def on_start(self):
        await super().on_start()


def serviceCreate(dotPath, config, parent: GService):
    return ProntoPairingService(dotPath=dotPath, config=config)
