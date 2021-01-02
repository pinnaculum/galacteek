from galacteek.core import runningApp
from galacteek.core.ps import keyServices
from galacteek.core.ps import KeyListener


class ServicesListener(KeyListener):
    listenTo = [keyServices]

    async def event_g_services(self, key, message):
        from galacteek.dweb.chanobjects.eth import EthSmartContractHandler

        app = runningApp()
        event = message['event']

        if event['type'] == 'ContractLoadedEvent':
            contract = event['contract']
            cConfig = event['contractConfig']

            webChannelName = cConfig.get('web3Channel', 'dpool')
            chanObjName = cConfig.get('web3ChanObjName', 'NOPE')

            channel = app.browserRuntime.web3Channel(
                webChannelName)

            handler = EthSmartContractHandler(contract['operator'],
                                              parent=app)
            handler.moveToThread(app.thread())

            channel.register(chanObjName, handler)
