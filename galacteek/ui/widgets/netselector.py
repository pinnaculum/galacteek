from PyQt5.QtWidgets import QMenu
from PyQt5.QtWidgets import QToolButton
from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QActionGroup
from PyQt5.QtCore import Qt
from galacteek.config.cmods import ipfs as cmodipfs

from galacteek.appsettings import *
from galacteek import partialEnsure
from galacteek.core import runningApp
from galacteek.dweb.markdown import markitdown

from ..dialogs import TextBrowserDialog
from ..dialogs import runDialogAsync

from ..helpers import getIcon
from ..helpers import messageBoxAsync

from ..i18n import iIpfsNetwork
from ..i18n import iCurrentIpfsNetwork
from ..i18n import iNoIpfsNetwork
from ..i18n import iUnknown


class IPFSNetworkSelectorToolButton(QToolButton):
    def __init__(self, icon=None, parent=None):
        super(IPFSNetworkSelectorToolButton, self).__init__(parent=parent)

        self.networksMenu = QMenu(iIpfsNetwork(), self)
        self.networksMenu.setIcon(getIcon('network.png'))
        self.networksActionGroup = QActionGroup(self.networksMenu)
        self.setEnabled(False)

        self.setObjectName('networkSelectorToolButton')
        self.setIcon(getIcon('network.png'))
        self.setText(iUnknown())
        self.setToolTip(iNoIpfsNetwork())
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.setPopupMode(QToolButton.InstantPopup)
        self.setMenu(self.networksMenu)

        self.networksActionGroup.triggered.connect(
            partialEnsure(self.onIpfsNetworkSwitch)
        )

    async def onIpfsNetworkSwitch(self, action, *args):
        app = runningApp()

        networkName = action.data()
        netCfg = cmodipfs.ipfsNetworkConfig(networkName)

        if not netCfg:
            return await messageBoxAsync(
                f'No infos on network: {networkName}'
            )

        covenant = netCfg.get('covenant', {})
        covenantEn = covenant.get('en')

        ipfsop = app.ipfsOperatorForLoop()

        if isinstance(covenantEn, str):
            acceptedCovenants = cmodipfs.ipfsNetworkAcceptedCovenants(
                networkName
            )

            entry = await ipfsop.hashComputeString(covenantEn)

            cid = entry['Hash'] if entry else None
            if cid and cid not in acceptedCovenants:
                # Show covenant dialog

                dlg = TextBrowserDialog(addButtonBox=True)
                dlg.setHtml(markitdown(covenantEn))

                await runDialogAsync(dlg)

                if dlg.result() == 1:
                    # Accepted
                    cmodipfs.ipfsNetworkAcceptCovenant(
                        networkName, cid
                    )
                else:
                    action.setChecked(False)

                    self.ipfsNetworkActionClearAllExcept(
                        app.ipfsd.ipfsNetworkName
                    )

                    return await messageBoxAsync(
                        f'Not joining network: {networkName}'
                    )

        if app.ipfsd:
            await app.ipfsd.switchNetworkByName(networkName)

            # Save the network name in the ini config
            # TODO: save in the yaml once we deprecate the ini

            app.settingsMgr.setSetting(
                CFG_SECTION_IPFSD,
                CFG_KEY_IPFS_NETWORK_NAME,
                networkName
            )

    def buildNetworksMenu(self):
        self.networksMenu.clear()
        try:
            for name, network in cmodipfs.ipfsNetworks():
                action = QAction(name, self.networksActionGroup)
                action.setData(name)
                action.setCheckable(True)
                self.networksActionGroup.addAction(action)
        except Exception:
            pass

        self.networksMenu.addActions(self.networksActionGroup.actions())

    def actionForIpfsNetwork(self, networkName):
        for action in self.networksActionGroup.actions():
            if action.data() == networkName:
                return action

    def ipfsNetworkActionClearAllExcept(self, networkName):
        for action in self.networksActionGroup.actions():
            action.setChecked(
                action.data() == networkName
            )

    async def processIpfsDaemonEvent(self, event):
        etype = event.get('type')

        if etype == 'IpfsDaemonStartedEvent':
            networkName = event.get('ipfsNetworkName')
            if not networkName:
                return

            self.ipfsNetworkActionClearAllExcept(networkName)
            self.setText(networkName)
            self.setToolTip(iCurrentIpfsNetwork(networkName))

            self.networksMenu.setEnabled(True)
            self.setEnabled(True)
        elif etype == 'IpfsDaemonStoppedEvent':
            self.setEnabled(False)
            self.setText(iUnknown())
            self.setToolTip(iNoIpfsNetwork())
