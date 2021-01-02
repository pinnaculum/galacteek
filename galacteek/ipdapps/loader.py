from galacteek import ensure

from galacteek import log
from galacteek.core.objects import GObject
from galacteek.ipdapps import availableDapps
from galacteek.ipdapps import dappGetModule
from galacteek.smartcontracts import getContractByName


class DappsRegistry(GObject):
    def __init__(self, ethService, parent=None):
        super().__init__(parent)
        self._dapps = {}
        self.ethService = ethService

    @property
    def ethCtrl(self):
        return self.ethService.ctrl

    async def loadDappFromAddr(self, dappName, contractName, address):
        lContract = getContractByName(contractName)
        if not lContract:
            return

        def load(_lContract, address):
            # Blocking call ?
            w3Contract = _lContract.web3Contract(self.web3)
            return w3Contract(address)

        contract = await self._e(load, lContract, address)
        if contract:
            return lContract.module.contractOperator(self, contract,
                                                     address, parent=self)
        else:
            log.debug('Contract invalid: {}'.format(address))

    async def loadDapp(self, dappName, **params):
        dapps = dict(availableDapps())
        dappPath = dapps.get(dappName, None)

        if not dappPath:
            return None

        module = dappGetModule(dappName)

        if module:
            dapp = module.Dapp(
                self.ethCtrl,
                dappName,
                dappPath,
                initModule=module,
                parent=self,
                **params
            )
            # dapp.pkgContentsChanged.connect(self.onDappPkgChanged)

            await dapp.registerSchemeHandlers()
            await dapp.dappInit()
            self._dapps[dappName] = dapp
            return dapp

    def onDappPkgChanged(self, dappName):
        dapp = self._dapps.get(dappName)
        if dapp:
            dapp.pkgContentsChanged.disconnect(self.onDappPkgChanged)
            dapp.reimportModule()
            dapp.stop()
            del self._dapps[dappName]

            ensure(self.loadDapp(dappName))
