from galacteek.appsettings import *
from . import SettingsFormController
from ..helpers import *


class SettingsController(SettingsFormController):
    """
    Last remaining form that uses the old appsettings.
    """

    qrcIcon = 'ipfs-cube-64.png'

    async def settingsInit(self):
        self.sManager = self.app.settingsMgr
        self.ui.pubsubRoutingMode.insertItem(0, ROUTER_TYPE_FLOOD)
        self.ui.pubsubRoutingMode.insertItem(1, ROUTER_TYPE_GOSSIP)
        self.ui.groupBoxDaemon.toggled.connect(self.onDaemonToggle)

        self.loadIpfsSettings()

        # Bulk connect
        for widget in [
                self.ui.ipfsdSwarmPort,
                self.ui.ipfsdSwarmPortQuic,
                self.ui.ipfsdApiPort,
                self.ui.ipfsdGwPort,
                self.ui.customIpfsApiPort,
                self.ui.customIpfsGwPort,
                self.ui.storageMax,
                self.ui.swarmMinConns,
                self.ui.swarmMaxConns]:

            widget.valueChanged.connect(self.onSaveIpfsSettings)

        for widget in [
                self.ui.routingMode,
                self.ui.pubsubRoutingMode]:

            widget.currentTextChanged.connect(self.onSaveIpfsSettings)

        for widget in [
                self.ui.checkBoxQuic,
                self.ui.keepDaemonRunning,
                self.ui.writableHttpGw,
                self.ui.acceleratedDht,
                self.ui.namesysPubsub,
                self.ui.fileStore]:

            widget.stateChanged.connect(self.onSaveIpfsSettings)

    def getS(self, section, key, type=None):
        return self.sManager.getSetting(section, key, type=type)

    def setS(self, section, key, value):
        return self.sManager.setSetting(section, key, value)

    def enableGroupDaemon(self):
        self.ui.groupBoxIpfsConn.setEnabled(False)
        self.ui.groupBoxDaemon.setEnabled(True)
        self.ui.groupBoxDaemon.setChecked(True)

        self.sManager.setTrue(CFG_SECTION_IPFSD, CFG_KEY_ENABLED)

    def enableGroupCustom(self):
        self.ui.groupBoxIpfsConn.setEnabled(True)
        self.ui.groupBoxDaemon.setChecked(False)

        self.sManager.setFalse(CFG_SECTION_IPFSD, CFG_KEY_ENABLED)

    def onSwarmMaxConns(self, value):
        minConns = self.ui.swarmMinConns.value()
        if value < minConns:
            self.ui.swarmMaxConns.setValue(minConns)

    def onDaemonToggle(self, on):
        if on:
            self.enableGroupDaemon()
        else:
            self.enableGroupCustom()

    def isChecked(self, w):
        return w.checkState() == Qt.Checked

    def setChecked(self, w, bVal):
        if bVal is True:
            w.setCheckState(Qt.Checked)
        else:
            w.setCheckState(Qt.Unchecked)

    def loadIpfsSettings(self):
        # IPFSD
        section = CFG_SECTION_IPFSD
        ipfsdEnabled = self.sManager.isTrue(section, CFG_KEY_ENABLED)

        if ipfsdEnabled:
            self.enableGroupDaemon()
        else:
            self.enableGroupCustom()

        self.ui.ipfsdSwarmPort.setValue(
            self.getS(section, CFG_KEY_SWARMPORT, int))
        self.ui.ipfsdSwarmPortQuic.setValue(
            self.getS(section, CFG_KEY_SWARMPORT_QUIC, int))

        self.setChecked(self.ui.checkBoxQuic,
                        self.sManager.isTrue(section, CFG_KEY_SWARM_QUIC))
        self.setChecked(self.ui.keepDaemonRunning,
                        self.sManager.isTrue(section, CFG_KEY_IPFSD_DETACHED))
        self.setChecked(self.ui.acceleratedDht,
                        self.sManager.isTrue(
                            section, CFG_KEY_ACCELERATED_DHT_CLIENT))

        self.ui.ipfsdApiPort.setValue(
            self.getS(section, CFG_KEY_APIPORT, int))
        self.ui.ipfsdGwPort.setValue(
            self.getS(section, CFG_KEY_HTTPGWPORT, int))
        self.ui.swarmMinConns.setValue(
            self.getS(section, CFG_KEY_SWARMLOWWATER, int))
        self.ui.swarmMaxConns.setValue(
            self.getS(section, CFG_KEY_SWARMHIGHWATER, int))
        self.ui.storageMax.setValue(
            self.getS(section, CFG_KEY_STORAGEMAX, int))
        self.ui.routingMode.setCurrentText(
            self.getS(section, CFG_KEY_ROUTINGMODE, str))
        self.ui.pubsubRoutingMode.setCurrentText(
            self.getS(section, CFG_KEY_PUBSUB_ROUTER, str))
        self.setChecked(self.ui.writableHttpGw,
                        self.sManager.isTrue(section, CFG_KEY_HTTPGWWRITABLE))
        self.setChecked(self.ui.namesysPubsub,
                        self.sManager.isTrue(section, CFG_KEY_NAMESYS_PUBSUB))
        self.setChecked(self.ui.fileStore,
                        self.sManager.isTrue(section, CFG_KEY_FILESTORE))

        # IPFS connection
        section = CFG_SECTION_IPFSCONN1
        self.ui.customIpfsHost.setText(
            self.getS(section, CFG_KEY_HOST, str))
        self.ui.customIpfsApiPort.setValue(
            self.getS(section, CFG_KEY_APIPORT, int))
        self.ui.customIpfsGwPort.setValue(
            self.getS(section, CFG_KEY_HTTPGWPORT, int))

    def onSaveIpfsSettings(self, *args):
        section = CFG_SECTION_IPFSD

        if self.ui.groupBoxDaemon.isChecked():
            self.sManager.setTrue(section, CFG_KEY_ENABLED)
        else:
            self.sManager.setFalse(section, CFG_KEY_ENABLED)

        self.setS(section, CFG_KEY_SWARMPORT, self.ui.ipfsdSwarmPort.text())
        self.setS(section, CFG_KEY_SWARMPORT_QUIC,
                  self.ui.ipfsdSwarmPortQuic.text())
        self.sManager.setBoolFrom(section, CFG_KEY_SWARM_QUIC,
                                  self.isChecked(self.ui.checkBoxQuic))
        self.setS(section, CFG_KEY_APIPORT, self.ui.ipfsdApiPort.text())
        self.setS(section, CFG_KEY_HTTPGWPORT, self.ui.ipfsdGwPort.text())
        self.setS(section, CFG_KEY_SWARMLOWWATER, self.ui.swarmMinConns.text())
        self.setS(
            section,
            CFG_KEY_SWARMHIGHWATER,
            self.ui.swarmMaxConns.text())
        self.setS(section, CFG_KEY_STORAGEMAX, self.ui.storageMax.text())
        self.setS(section, CFG_KEY_ROUTINGMODE,
                  self.ui.routingMode.currentText())
        self.setS(section, CFG_KEY_PUBSUB_ROUTER,
                  self.ui.pubsubRoutingMode.currentText())
        self.sManager.setBoolFrom(section, CFG_KEY_HTTPGWWRITABLE,
                                  self.isChecked(self.ui.writableHttpGw))
        self.sManager.setBoolFrom(section, CFG_KEY_NAMESYS_PUBSUB,
                                  self.isChecked(self.ui.namesysPubsub))
        self.sManager.setBoolFrom(section, CFG_KEY_FILESTORE,
                                  self.isChecked(self.ui.fileStore))
        self.sManager.setBoolFrom(section, CFG_KEY_IPFSD_DETACHED,
                                  self.isChecked(self.ui.keepDaemonRunning))
        self.sManager.setBoolFrom(section, CFG_KEY_ACCELERATED_DHT_CLIENT,
                                  self.isChecked(self.ui.acceleratedDht))

        section = CFG_SECTION_IPFSCONN1
        self.setS(section, CFG_KEY_HOST, self.ui.customIpfsHost.text())
        self.setS(section, CFG_KEY_APIPORT, self.ui.customIpfsApiPort.text())
        self.setS(section, CFG_KEY_HTTPGWPORT, self.ui.customIpfsGwPort.text())
