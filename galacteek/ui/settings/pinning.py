
from PyQt5.QtWidgets import QListWidgetItem

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QObject
from PyQt5.QtCore import pyqtSignal

# from galacteek.ui.forms.ui_settings_pinning import

from galacteek.config.cmods import pinning as cfgpinning

from galacteek.ipfs import ipfsOp
from galacteek import ensure
from galacteek import partialEnsure
from galacteek import database
from galacteek.core import runningApp
from galacteek.config import Configurable
from galacteek.ui.dialogs.pinning import PinningServiceAddDialog
from galacteek.ui.helpers import runDialogAsync
from galacteek.ui.helpers import messageBoxAsync


class SettingsController(QObject, Configurable):
    configModuleName = 'galacteek.ipfs.pinning'

    def __init__(self, sWidget, parent=None):
        super().__init__(sWidget)

        self.app = runningApp()
        self.sWidget = sWidget

        self.sWidget.ui.rPinServiceAddButton.clicked.connect(
            partialEnsure(self.onNewRemoteService))

    @property
    def sListView(self):
        return self.sWidget.ui.rPinServices

    def configApply(self, config):
        services = cfgpinning.rpsList()
        print('config changed ..')
        ensure(self.refreshServices(services))

    async def settingsInit(self):
        # await self.refreshServices(cfgpinning.rpsList())
        self.cApply()

    async def refreshServicesOld(self):
        services = await database.remotePinningServicesList()
        for service in services:
            found = self.sListView.findItems(
                service.name,
                Qt.MatchExactly
            )
            if len(found):
                continue

            self.sListView.addItem(QListWidgetItem(service.name))

    async def refreshServices(self, services):
        # services = cfgpinning.rpsList()
        print('HAVE', services)

        for service in services:
            found = self.sListView.findItems(
                service.displayName,
                Qt.MatchExactly
            )
            if len(found):
                continue

            print('Adding service in list', service)
            self.sListView.addItem(QListWidgetItem(service.displayMame))

    @ipfsOp
    async def onNewRemoteServiceOld(self, ipfsop, *args):
        dialog = PinningServiceAddDialog()
        await runDialogAsync(dialog)

        options = dialog.options()

        if not options:
            return await messageBoxAsync('Invalid')

        service = await database.remotePinningServiceAdd(
            options['name'],
            options['endpoint'],
            options['secret']
        )

        if not service:
            return await messageBoxAsync('Invalid')

        print(service)
        result = await ipfsop.pinRemoteServiceAdd(
            service.name,
            service.endpoint,
            service.key
        )
        print(result)

        await self.refreshServices()

    @ipfsOp
    async def onNewRemoteService(self, ipfsop, *args):
        dialog = PinningServiceAddDialog()
        await runDialogAsync(dialog)

        if dialog.result() != 1:
            print('canceled')
            return

        options = dialog.options()

        if not options:
            return await messageBoxAsync('Invalid')

        try:
            assert options['name'] is not None
            assert options['endpoint'] is not None
            assert options['secret'] is not None

            result = await ipfsop.pinRemoteServiceAdd(
                options['name'],
                options['endpoint'],
                options['secret']
            )
            print(result)
        except Exception as err:
            return await messageBoxAsync('ERR')

        await self.app.s.ldPublish({
            'type': 'RPSConfigChanged'
        })

        await self.refreshServices()
