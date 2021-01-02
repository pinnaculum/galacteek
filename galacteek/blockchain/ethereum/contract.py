import asyncio
import attr
from galacteek import log
from galacteek.core.aservice import GService
from galacteek.core.ps import makeKeySmartContract
from galacteek.core.ps import gHub
from web3 import Account


class AutoContractDeployer:
    def contractDeploy(self, w3, contract_interface):
        try:
            if 'bytecode' in contract_interface:
                binary = contract_interface['bytecode']
            elif 'bin' in contract_interface:
                binary = contract_interface['bin']
            else:
                raise ValueError('Invalid contract interface')

            contract = w3.eth.contract(
                abi=contract_interface['abi'],
                bytecode=binary)

            txHash = contract.constructor().transact()
            address = w3.eth.getTransactionReceipt(txHash)['contractAddress']
            return address
        except Exception as err:
            print(str(err))
            log.debug(f'Failed to deploy contract: {err}')
            return None


class Deployer:
    def __init__(self, w3, contract_interface, public_key, private_key):
        self.w3 = w3

        if 'bytecode' in contract_interface:
            self.bin = contract_interface['bytecode']
        elif 'bin' in contract_interface:
            self.bin = contract_interface['bin']

        self.abi = contract_interface['abi']
        self.priv = private_key
        self.pub = public_key

    def deploy(self):
        contract = self.w3.eth.contract(abi=self.abi, bytecode=self.bin)

        acct = Account.privateKeyToAccount(self.priv)
        contract_data = contract.constructor().buildTransaction(
            {'from': acct.address,
             'gasPrice': self.w3.eth.gasPrice,
             'gas': 10}
        )
        contract_data["nonce"] = self.w3.eth.getTransactionCount(
            acct.address)

        try:
            signed = self.w3.eth.account.signTransaction(
                contract_data, self.priv)
            tx_hash = self.w3.eth.sendRawTransaction(signed.rawTransaction)
        except ValueError as verr:
            log.debug(f'sendRawTransaction error: {verr}')
        else:
            return tx_hash.hex()


def contractDeploy(w3, contract_interface):
    try:
        if 'bytecode' in contract_interface:
            binary = contract_interface['bytecode']
        elif 'bin' in contract_interface:
            binary = contract_interface['bin']
        else:
            raise ValueError('Invalid contract interface')

        contract = w3.eth.contract(
            abi=contract_interface['abi'],
            bytecode=binary)

        txHash = contract.constructor().transact()
        address = w3.eth.getTransactionReceipt(txHash)['contractAddress']
        return address
    except Exception as err:
        log.debug(f'Failed to deploy contract: {err}')
        return None


@attr.s(auto_attribs=True)
class OperatorMixin:
    contract: None
    txTimeout: int = 180
    filters: list = []

    def getFunc(self, fnName: str):
        return getattr(self.contract.functions, fnName)

    def _trwrap(self, func, *args):
        fn = self.getFunc(func)
        try:
            txHash = fn(*args).transact()
            receipt = self.ctrl.web3.eth.waitForTransactionReceipt(
                txHash, self.txTimeout)
            return receipt
        except Exception as err:
            log.debug(f'Transaction call: {func} failed with error: {err}')

    def callFunction(self, fnName, *args):
        fn = self.getFunc(fnName)
        if fn:
            result = fn(*args).call()
            return result

    def callFunctionTransact(self, fnName, *args):
        fn = self.getFunc(fnName)
        if fn:
            return self._trwrap(fnName, *args)

    def buildEventFilter(self, eventName, fromBlock=0):
        try:
            ev = getattr(self.contract.events, eventName)
            if not ev:
                raise Exception(f'Event {eventName} does not exist')

            filter_builder = ev.build_filter()
            filter_builder.fromBlock = fromBlock
            ethFilter = filter_builder.deploy(self.ctrl.web3)
        except Exception as err:
            log.debug(str(err))
        else:
            return ethFilter


class ContractOperator(GService, OperatorMixin):
    def __init__(self, ctrl, contract, address, parent=None,
                 contractName=None):
        GService.__init__(self)
        OperatorMixin.__init__(self, contract=contract)

        self.ctrl = ctrl
        self.address = address
        self.psKey = makeKeySmartContract(
            contractName if contractName else 'unknown',
            address
        )

    async def on_start(self):
        log.debug(f'Contract operator: {self.contract} at {self.address}'
                  ': starting')
        await self.init()

    async def call(self, fn, *args):
        def _callwrap(func, *args):
            result = func(*args).call()
            return result

        return await self.ctrl._e(_callwrap, fn, *args)

    async def transact(self, fn, *args):
        def _trwrap(func, *args):
            fn = self.getFunc(func)
            txHash = fn(*args).transact()
            receipt = self.ctrl.web3.eth.waitForTransactionReceipt(txHash, 180)
            return receipt

        return await self.ctrl._e(_trwrap, fn, *args)

    async def callByName(self, fnName, *args, **kw):
        fn = getattr(self.contract.functions, fnName)
        if fn:
            return await self.call(fn, *args)

    async def callTrByName(self, fnName, *args, **kw):
        fn = getattr(self.contract.functions, fnName)
        if fn:
            return await self.transact(fn, *args)

    async def script(self, fn, *args, **kw):
        r = await self.ctrl._e(fn, self.ctrl.web3, self.contract, *args, **kw)
        return r

    @GService.task
    async def processFilters(self):
        """
        Filters process task
        """

        while not self.should_stop:
            await asyncio.sleep(5)

            for filter in self.filters:
                for event in filter.get_all_entries():

                    # Push to the hub
                    gHub.publish(self.psKey, event)
