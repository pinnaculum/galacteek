import attr

from galacteek import log
from galacteek.browser.web3channels import Web3Channel
from galacteek.browser.web3channels import Web3Transport

from galacteek.browser import pslisteners
from galacteek.browser.interceptor import IPFSRequestInterceptor


@attr.s(auto_attribs=True)
class BrowserRuntimeObjects:
    web3Transport: Web3Transport = Web3Transport()
    web3Channels: dict = {}
    # XXX
    # web3ContractHandlers = weakref.WeakValueDictionary()
    web3ContractHandlers = dict = {}

    ipfsCeptor: IPFSRequestInterceptor = None

    app: object = None

    def storeContractHandler(self, name, handler):
        self.web3ContractHandlers[name] = handler

    def web3Channel(self, name: str):
        """
        Returns a web3 channel for the given name
        """

        c = self.web3Channels.get(name)
        if not c:
            self.web3Channels[name] = Web3Channel(self.app)
            self.web3Channels[name].moveToThread(self.app.thread())

            log.debug(f'Web3 channel register {name}: '
                      f'{self.web3Channels[name]}')

        return self.web3Channels[name]

    def web3ChannelClone(self, name: str):
        return self.web3Channel(name).clone()


async def browserSetup(app, runtime: BrowserRuntimeObjects):
    listener = pslisteners.ServicesListener()
    log.debug(f'Services listener: {listener}')
