import asyncio

from PyQt5.QtWidgets import QListWidgetItem

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QObject

from galacteek.config.cmods import pinning as cfgpinning

from galacteek.ipfs import ipfsOp
from galacteek import ensure
from galacteek import partialEnsure
from galacteek import database
from galacteek.core import runningApp
from galacteek.core.ps import KeyListener
from galacteek.config import Configurable
from galacteek.ui.dialogs.pinning import PinningServiceAddDialog
from galacteek.ui.helpers import runDialogAsync
from galacteek.ui.helpers import messageBoxAsync
from galacteek.ui.widgets import IconSelector


class SettingsController(QObject, Configurable, KeyListener):
    configModuleName = 'galacteek.ipfs.pinning'

    def __init__(self, sWidget, parent=None):
        super().__init__(sWidget)

        self.app = runningApp()
        self.currentServiceItem = None
        self.sWidget = sWidget

        self.sWidget.ui.removeService.setEnabled(False)
        self.sWidget.ui.rServiceConfigGroup.setEnabled(False)

        self.sWidget.ui.rPinServiceAddButton.clicked.connect(
            partialEnsure(self.onNewRemoteService))
        self.sWidget.ui.removeService.clicked.connect(
            partialEnsure(self.onRemoveService))
        self.sWidget.ui.rPinServices.currentItemChanged.connect(
            self.onCurrentServiceChanged)

        self.iconSelector = IconSelector()
        self.sWidget.ui.srvGridLayout.addWidget(
            self.iconSelector,
            1, 1
        )

        self.sWidget.ui.rpsPriority.valueChanged.connect(self.servicePatch)
        self.iconSelector.iconSelected.connect(self.servicePatch)

    @property
    def sListView(self):
        return self.sWidget.ui.rPinServices

    @property
    def ui(self):
        return self.sWidget.ui

    @property
    def sCurItem(self):
        return self.currentServiceItem

    def configApply(self, config):
        services = cfgpinning.rpsList()
        ensure(self.refreshServices(services))

    async def event_g_services_app(self, key, message):
        event = message['event']

        if event['type'] == 'RPSConfigChanged':
            await self.refreshServices(cfgpinning.rpsList())

    async def settingsInit(self):
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
        for service in services:
            found = self.sListView.findItems(
                service.displayName,
                Qt.MatchExactly
            )
            if len(found):
                continue

            self.sListView.addItem(QListWidgetItem(service.displayName))

    @ipfsOp
    async def onRemoveService(self, ipfsop, *args):
        current = self.sListView.currentItem()
        if not current:
            return

        sDisplayName = current.text()
        service = cfgpinning.rpsByDisplayName(sDisplayName)

        if service:
            await ipfsop.pinRemoteServiceRemove(
                service.serviceName)

        self.sListRemoveSelected()

    def onCurrentServiceChanged(self, current, previous):
        if not current:
            return

        self.currentServiceItem = current

        service = cfgpinning.rpsByDisplayName(current.text())
        if service:
            self.ui.removeService.setEnabled(True)
            self.ui.rServiceConfigGroup.setEnabled(True)

            self.serviceSettingsUpdate(service)
            self.ui.rServiceConfigGroup.setTitle(service.displayName)

    def serviceSettingsUpdate(self, service):
        self.ui.rpsPriority.setValue(service.priority)

    def servicePatch(self, *args):
        """
        Set the settings for the current service from the UI
        """
        if not self.sCurItem:
            return

        service = cfgpinning.rpsByDisplayName(self.sCurItem.text())
        if service:
            service.priority = self.ui.rpsPriority.value()

            iconCid = self.iconSelector.iconCid
            if iconCid:
                service.iconCid = iconCid

        cfgpinning.configSave()

    def sListRemoveSelected(self):
        # Remove the currently selected item in the services view

        listItems = self.sListView.selectedItems()
        if not listItems:
            return

        for item in listItems:
            self.sListView.takeItem(self.sListView.row(item))

    @ipfsOp
    async def onNewRemoteService(self, ipfsop, *args):
        dialog = PinningServiceAddDialog()
        await runDialogAsync(dialog)

        if dialog.result() != 1:
            return

        options = dialog.options()

        if not options:
            return await messageBoxAsync('Invalid')

        try:
            assert options['name'] is not None
            assert options['endpoint'] is not None
            assert options['secret'] is not None

            await ipfsop.pinRemoteServiceAdd(
                options['name'],
                options['endpoint'],
                options['secret']
            )
        except Exception:
            return await messageBoxAsync('ERR')
        else:
            await asyncio.sleep(0.2)

            await self.app.s.ldPublish({
                'type': 'RPSAdded'
            })

            await messageBoxAsync('OK')
