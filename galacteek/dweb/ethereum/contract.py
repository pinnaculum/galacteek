from solcx import compile_source

from galacteek import log


def solCompileFile(file_path):
    try:
        with open(file_path, 'r') as f:
            source = f.read()

        return compile_source(source)
    except Exception as err:
        log.debug(str(err))


def contractDeploy(w3, contract_interface):
    tx_hash = w3.eth.contract(
        abi=contract_interface['abi'],
        bytecode=contract_interface['bin']).deploy()

    address = w3.eth.getTransactionReceipt(tx_hash)['contractAddress']
    return address


class LocalContract:
    def __init__(self, solPath):
        self.solSourcePath = solPath
        self._deployedAddress = None

    @property
    def sol(self):
        return self.solSourcePath

    @property
    def address(self):
        return self._deployedAddress

    @address.setter
    def address(self, addr):
        self._deployedAddress = addr

    def __repr__(self):
        return 'Local contract: {}'.format(self.solSourcePath)


class ContractWrapper:
    def __init__(self, ctrl, contract):
        self.ctrl = ctrl
        self.contract = contract

    async def call(self, fn, *args, **kw):
        txhash = fn.transact()
        receipt = self.ctrl.web3.eth.waitForTransactionReceipt(txhash)
        return receipt
