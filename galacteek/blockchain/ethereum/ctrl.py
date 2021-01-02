import functools
import asyncio
import concurrent.futures
import async_timeout
import time
from yarl import URL

from eth_keys import keys
from web3 import Web3
from web3.providers.websocket import WebsocketProvider
from web3.auto import w3
from web3.middleware import geth_poa_middleware

from ens import ENS

from PyQt5.QtWidgets import QApplication

from galacteek import log
from galacteek import logUser
from galacteek import ensure
from galacteek import AsyncSignal
from galacteek.config import dictconfig

from .contract import ContractOperator
from .account import createWithMnemonic

from galacteek.smartcontracts import listContracts
from galacteek.smartcontracts import getContractByName
from galacteek.smartcontracts import getContractDeployments

from requests.exceptions import ConnectionError


class EthBlock:
    def __init__(self, block):
        self._block = block


def web3Connect(params: dictconfig.DictConfig):
    from galacteek.blockchain.ethereum.infura import endpoints

    if params.provType in ['http', 'https']:
        scheme = 'https'
    elif params.provType == 'websocket':
        scheme = 'ws'
    else:
        scheme = 'https'

    if params.mode == 'infura':
        projectId = params.infura.projectId
        projectSecret = params.infura.projectSecret

        if scheme == 'ws':
            url = URL.build(
                host=endpoints.INFURA_RINKEBY_DOMAIN,
                scheme=scheme,
                user='',
                password=projectSecret,
                path=f'/ws/v3/{projectId}'
            )
        elif scheme == 'https':
            url = URL.build(
                host='rinkeby.infura.io',
                scheme=scheme,
                user='',
                password=projectSecret,
                path=f'/v3/{projectId}'
            )
    elif params.mode in ['manual', 'ganache']:
        url = URL(params.rpcUrl)

    urlString = str(url)
    log.debug(f'Using web3 provider URL: {urlString}')

    if scheme == 'https':
        w3 = Web3(Web3.HTTPProvider(urlString))
    elif scheme == 'websocket':
        w3 = Web3(WebsocketProvider(urlString))
    else:
        return None

    if params.mode == 'infura':
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    return w3


class EthereumController:
    ethConnected = AsyncSignal(bool)
    ethNewBlock = AsyncSignal(str)

    def __init__(self, connParams, web3=None, loop=None,
                 executor=None, parent=None):
        self.app = QApplication.instance()

        self.loop = loop if loop else asyncio.get_event_loop()
        self.executor = executor if executor else \
            concurrent.futures.ThreadPoolExecutor(max_workers=4)

        self._params = connParams
        self._web3 = web3
        self._watchTask = None
        self._blockLatest = None
        self._stop = False
        self._loadedContracts = {}

        self._accountCurrent = None

    @property
    def web3(self):
        return self._web3

    @property
    def params(self):
        return self._params

    @property
    def currentAccount(self):
        return self._accountCurrent

    @property
    def currentPrivKey(self):
        if self.currentAccount:
            return keys.PrivateKey(self.currentAccount.key)

    @property
    def currentPubKey(self):
        if self.currentAccount:
            pk = keys.PrivateKey(self.currentAccount.key)
            return pk.public_key.to_hex()

    def changeParams(self, params):
        self._params = params

    def getWeb3(self):
        try:
            web3 = web3Connect(self.params)

            if not web3:
                raise Exception(
                    f'unsupported provType {self._params.provType}')

            account = None
            try:
                if hasattr(web3, 'personal') and web3.personal.listAccounts:
                    # Geth Node
                    account = web3.personal.listAccounts[0]
                else:
                    account = web3.eth.accounts[0]
                    # raise Exception('Nothing ..')
            except Exception:
                log.debug('No eth account found')
                self.createAccount(web3)
            else:
                web3.eth.defaultAccount = account

            log.debug(f'Using account {account}', account)

            self._ns = ENS.fromWeb3(web3)
            return web3
        except Exception as err:
            log.debug('Cannot get Web3 connector: {}'.format(str(err)))
            return None

    def createAccount(self, web3):
        acct, mnemonic = createWithMnemonic()
        web3.eth.defaultAccount = acct.address
        self._accountCurrent = acct
        log.debug(f'Created account {acct.address}')

    async def _e(self, fn, *args, **kw):
        timeout = kw.pop('timeout', None)
        try:
            if isinstance(timeout, int):
                with async_timeout.timeout(timeout):
                    return await self.loop.run_in_executor(
                        self.executor, functools.partial(fn, *args, **kw))
            else:
                return await self.loop.run_in_executor(
                    self.executor, functools.partial(fn, *args, **kw))
        except asyncio.TimeoutError:
            log.debug('ETH Timeout')
        except ConnectionError:
            log.debug(
                'ETH Connection error while running fn: {0}'.format(fn))
            return None

    # API coroutines

    async def stop(self):
        self._stop = True
        self._web3 = None

    async def start(self):
        if not self._web3:
            self._web3 = self.getWeb3()

        if self.web3 is None:
            log.debug('Web3 invalid')
            return

        if await self.connected():
            logUser.info('Ethereum: connected to {}'.format(
                self.params.rpcUrl))
            await self.ethConnected.emit(True)

            self._watchTask = ensure(self._e(self.watchTask))

            ensure(self.loadAutoDeploy())
            # await self.loadContracts()
        else:
            await self.ethConnected.emit(False)

    async def latestBlock(self):
        return await self._e(self.web3.eth.getBlock, 'latest')

    async def getBlock(self, block='latest'):
        return EthBlock(await self._e(self.web3.eth.getBlock, block))

    async def connected(self):
        return self.web3 and await self._e(self.web3.isConnected)

    async def ensAddress(self, name):
        return await self._e(self._ns.address, name)

    def watchTask(self):
        return

        try:
            blkfilter = self.web3.eth.filter('latest')
        except Exception:
            # Node does not support filters ?
            return

        while not self._stop:
            time.sleep(5)

            for event in blkfilter.get_new_entries():
                self.eventLatestBlock(event)

    def eventLatestBlock(self, event):
        if isinstance(event, bytes):
            blockHex = w3.toHex(event)

            # Use emitSafe() (thread-safe, we are called from watchTask())
            self.ethNewBlock.emitSafe(blockHex)

    async def loadAutoDeploy(self):
        # NOT USED
        # Load contracts with autoload=True

        for lContract in listContracts():
            dList = getContractDeployments(lContract.name, autoload=True)

            for depl in dList:
                log.debug('Loading auto-deployment for contract {}'.format(
                    lContract.name))
                contract, cOperator = await self.loadLocalContractFromAddr(
                    lContract.name, depl['address'])

    async def loadContractFromAddress(self, address: str, abi):
        def load(addr, abi):
            contract = self.web3.eth.contract(
                address=addr,
                abi=abi
            )
            return ContractOperator(self, contract, addr)
        return await self._e(load, address, abi)

    async def loadLocalContractFromDeployment(self, contractName: str):
        if not await self.connected():
            raise Exception('Not connected!')

        lContract = getContractByName(contractName)
        if not lContract:
            return

        deployments = getContractDeployments(contractName)
        if len(deployments) > 0:
            depl = deployments.pop()
            return await self.loadLocalContractFromAddr(
                contractName,
                depl['address']
            )

        return None, None

    async def loadLocalContractFromAddr(self, contractName: str,
                                        address: str):
        if not await self.connected():
            raise Exception('Not connected!')

        lContract = getContractByName(contractName)
        if not lContract:
            return None, None

        def load(_lContract, address):
            # Blocking call
            w3Contract = _lContract.web3Contract(self.web3)
            return w3Contract(address)

        contract = await self._e(load, lContract, address)
        if contract:
            operator = lContract.module.contractOperator(
                self, contract,
                address, parent=self,
                contractName=contractName
            )
            self._loadedContracts.setdefault(contractName, {'default': None})
            self._loadedContracts[contractName][address] = operator

            if self._loadedContracts[contractName]['default'] is None:
                self._loadedContracts[contractName]['default'] = operator

            log.debug('Contract {0} loaded at {1}'.format(
                contractName, address))
            return lContract, operator
        else:
            log.debug('Contract invalid: {}'.format(address))
            return None, None

    def getDefaultLoadedOperator(self, contractName: str):
        loaded = self._loadedContracts.get(contractName)
        if loaded:
            return loaded.get('default')
