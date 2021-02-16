import asyncio

from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QTreeWidget
from PyQt5.QtWidgets import QTreeWidgetItem
from PyQt5.QtWidgets import QHeaderView
from PyQt5.QtWidgets import QStyledItemDelegate
from PyQt5.QtWidgets import QSpinBox
from PyQt5.QtWidgets import QDoubleSpinBox
from PyQt5.QtWidgets import QComboBox
from PyQt5.QtWidgets import QLabel

from PyQt5.QtCore import Qt
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QUrl
from PyQt5.QtCore import QSize
from PyQt5.QtCore import QModelIndex

from galacteek.config import configModLeafAttributes
from galacteek.config import configModules
from galacteek.config import cGet
from galacteek.config import cSet

from galacteek import ensureSafe
from galacteek import partialEnsure

from .widgets import GalacteekTab
from .forms import ui_settings
from .themes import themesList
from ..appsettings import *
from .helpers import *
from .i18n import *


class SettingsDialog(QDialog):
    def __init__(self, app, parent=None):
        super().__init__(parent)

        self.app = app
        self.sManager = self.app.settingsMgr

        self.ui = ui_settings.Ui_SettingsDialogForm()
        self.ui.setupUi(self)
        self.ui.groupBoxDaemon.toggled.connect(self.onDaemonToggle)
        self.ui.changeDownloadsPathButton.clicked.connect(
            self.onChangeDownloadsPath)

        self.ui.pubsubRoutingMode.insertItem(0, ROUTER_TYPE_FLOOD)
        self.ui.pubsubRoutingMode.insertItem(1, ROUTER_TYPE_GOSSIP)

        self.loadSettings()

        self.ui.themeCombo.currentTextChanged.connect(
            self.onThemeSelectionChanged)
        self.ui.swarmMaxConns.valueChanged.connect(self.onSwarmMaxConns)

        self.setMinimumSize(
            (2 * self.app.desktopGeometry.height()) / 3,
            (3 * self.app.desktopGeometry.height()) / 4
        )

    def enableGroupDaemon(self):
        self.ui.groupBoxIpfsConn.setEnabled(False)
        self.ui.groupBoxDaemon.setEnabled(True)
        self.ui.groupBoxDaemon.setChecked(True)

    def enableGroupCustom(self):
        self.ui.groupBoxIpfsConn.setEnabled(True)
        self.ui.groupBoxDaemon.setChecked(False)

    def onSwarmMaxConns(self, value):
        minConns = self.ui.swarmMinConns.value()
        if value < minConns:
            self.ui.swarmMaxConns.setValue(minConns)

    def onChangeDownloadsPath(self):
        dirSel = directorySelect()
        if dirSel:
            self.ui.downloadsLocation.setText(dirSel)
            self.setS(CFG_SECTION_BROWSER, CFG_KEY_DLPATH, dirSel)

    def onDaemonToggle(self, on):
        if on:
            self.enableGroupDaemon()
        else:
            self.enableGroupCustom()

    def getS(self, section, key, type=None):
        return self.sManager.getSetting(section, key, type=type)

    def isChecked(self, w):
        return w.checkState() == Qt.Checked

    def setChecked(self, w, bVal):
        if bVal is True:
            w.setCheckState(Qt.Checked)
        else:
            w.setCheckState(Qt.Unchecked)

    def setS(self, section, key, value):
        return self.sManager.setSetting(section, key, value)

    def onThemeSelectionChanged(self, themeName):
        self.applyTheme(themeName)

    def loadSettings(self):
        # lang

        langCodeCurrent = cGet(
            'language',
            mod='galacteek.application'
        )

        langsAvailable = cGet(
            'languagesAvailable',
            mod='galacteek.application'
        )

        for langEntry in langsAvailable:
            langCode = langEntry.get('code')
            langDisplayName = langEntry.get('displayName')

            self.ui.language.addItem(
                langDisplayName,
                langCode
            )

        for idx in range(self.ui.language.count()):
            code = self.ui.language.itemData(idx)
            if code == langCodeCurrent:
                self.ui.language.setCurrentIndex(idx)

        # Theme

        self.ui.themeCombo.clear()

        for themeName, tPath in themesList():
            self.ui.themeCombo.addItem(themeName)

        curTheme = cGet('theme', mod='galacteek.ui')
        if curTheme:
            self.ui.themeCombo.setCurrentText(curTheme)

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

        # Browser
        section = CFG_SECTION_BROWSER
        self.ui.home.setText(
            self.getS(section, CFG_KEY_HOMEURL, str))
        self.ui.downloadsLocation.setText(
            self.getS(section, CFG_KEY_DLPATH, str))

        # Default web profile combo box

        currentDefault = cGet('defaultWebProfile',
                              mod='galacteek.browser.webprofiles')
        pNameList = self.app.availableWebProfilesNames()

        for pName in pNameList:
            self.ui.comboDefaultWebProfile.insertItem(
                self.ui.comboDefaultWebProfile.count(),
                pName
            )

        if currentDefault and currentDefault in pNameList:
            self.ui.comboDefaultWebProfile.setCurrentText(currentDefault)

        # History
        self.setChecked(self.ui.urlHistoryEnable,
                        self.sManager.isTrue(CFG_SECTION_HISTORY,
                                             CFG_KEY_HISTORYENABLED))
        # UI
        self.ui.webEngineDefaultZoom.setValue(
            cGet('zoom.default', mod='galacteek.ui.browser'))

        # Eth
        section = CFG_SECTION_ETHEREUM
        ethEnabled = self.sManager.isTrue(section, CFG_KEY_ENABLED)

        if ethEnabled:
            self.ui.groupBoxEth.setEnabled(True)
            self.ui.groupBoxEth.setChecked(True)

        self.ui.ethProvType.setCurrentText(
            self.sManager.getSetting(section, CFG_KEY_PROVIDERTYPE))
        self.ui.ethRpcUrl.setText(
            self.sManager.getSetting(section, CFG_KEY_RPCURL))

    def accept(self):
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

        section = CFG_SECTION_IPFSCONN1
        self.setS(section, CFG_KEY_HOST, self.ui.customIpfsHost.text())
        self.setS(section, CFG_KEY_APIPORT, self.ui.customIpfsApiPort.text())
        self.setS(section, CFG_KEY_HTTPGWPORT, self.ui.customIpfsGwPort.text())

        section = CFG_SECTION_BROWSER
        self.setS(section, CFG_KEY_HOMEURL, self.ui.home.text())

        cSet('defaultWebProfile',
             self.ui.comboDefaultWebProfile.currentText(),
             mod='galacteek.browser.webprofiles')

        section = CFG_SECTION_HISTORY
        cSet('enabled', self.isChecked(self.ui.urlHistoryEnable),
             mod='galacteek.ui.history')

        cSet('zoom.default', self.ui.webEngineDefaultZoom.value(),
             mod='galacteek.ui.browser')

        idx = self.ui.language.currentIndex()
        langCode = self.ui.language.itemData(idx)

        curLang = cGet('language', mod='galacteek.application')
        if langCode != curLang:
            cSet('language', langCode, mod='galacteek.application')
            self.app.setupTranslator()

        section = CFG_SECTION_ETHEREUM

        if self.ui.groupBoxEth.isChecked():
            self.sManager.setTrue(section, CFG_KEY_ENABLED)
        else:
            self.sManager.setFalse(section, CFG_KEY_ENABLED)

        rpcUrl = QUrl(self.ui.ethRpcUrl.text())

        if not rpcUrl.isValid() or not rpcUrl.scheme() in [
                'http', 'https', 'wss'] or not rpcUrl.host():
            return messageBox(
                'Invalid Ethereum RPC URL (scheme should be http or wss)'
            )

        self.setS(section, CFG_KEY_PROVIDERTYPE,
                  self.ui.ethProvType.currentText())
        self.setS(section, CFG_KEY_RPCURL, rpcUrl.toString())

        self.app.urlHistory.historyConfigChanged.emit(
            self.sManager.urlHistoryEnabled)

        self.sManager.sync()
        self.sManager.changed = True

        self.done(1)

    def applyTheme(self, themeName: str):
        cSet('theme', themeName, mod='galacteek.ui')

        self.app.themes.change(themeName)

    async def applySettingsEth(self):
        self.app.ethereum.changeParams(self.app.getEthParams())

        if self.sManager.isTrue(CFG_SECTION_ETHEREUM, CFG_KEY_ENABLED):
            if not await self.app.ethereum.connected():
                await self.app.ethereum.start()

    def reject(self):
        self.done(0)


ModRole = Qt.UserRole + 1
AttrRole = Qt.UserRole + 2
AttrTypeRole = Qt.UserRole + 3


class ConfigItemDelegate(QStyledItemDelegate):
    INT_MAX = 2147483647

    attributeChanged = pyqtSignal(QModelIndex)

    def __init__(self, parent):
        super().__init__(parent)
        self.model = parent.model()
        self.tree = parent

    def _tr(self, index):
        mod = self.model.data(index, ModRole)
        attr = self.model.data(index, AttrRole)
        atype = self.model.data(index, AttrTypeRole)
        return mod, attr, atype

    def setEditorData(self, editor, index):
        mod, attr, atype = self._tr(index)
        value = cGet(attr, mod=mod)

        if isinstance(editor, QSpinBox) or isinstance(editor, QDoubleSpinBox):
            editor.setValue(value)

        if isinstance(editor, QComboBox):
            editor.setCurrentText(str(value))

    def setModelData(self, editor, model, index):
        mod, attr, atype = self._tr(index)

        if isinstance(editor, QSpinBox) or isinstance(editor, QDoubleSpinBox):
            cSet(attr, editor.value(), mod=mod)
            self.attributeChanged.emit(index)
        elif isinstance(editor, QComboBox):
            if editor.currentText() == str(True):
                cSet(attr, True, mod=mod)
            else:
                cSet(attr, False, mod=mod)
            self.attributeChanged.emit(index)

    def createEditor(self, parent, option, index):
        mod, attr, atype = self._tr(index)

        if atype is int:
            editor = QSpinBox(parent)
            editor.setMinimum(0)
            editor.setMaximum(self.INT_MAX)
            editor.setSingleStep(1)

            # Icons
            if attr.lower().endswith('iconsize'):
                editor.setSingleStep(8)
        elif atype is float:
            editor = QDoubleSpinBox(parent)
            editor.setMinimum(0)
            editor.setMaximum(float(self.INT_MAX))
            editor.setSingleStep(0.1)
        elif atype is bool:
            editor = QComboBox(parent)
            editor.addItem(str(True))
            editor.addItem(str(False))
        else:
            return None

        return editor

    def destroyEditor(self, editor, index):
        editor.deleteLater()

    def displayText(self, value, locale):
        return str(value)

    def sizeHint(self, option, index):
        return QSize(
            self.tree.width() / 8,
            32
        )


class ConfigModuleItem(QTreeWidgetItem):
    pass


class ConfigManager(GalacteekTab):
    COL_ATTR = 0
    COL_EDITOR = 1
    COL_STATUS = 2

    def tabSetup(self):
        self.setContentsMargins(8, 8, 8, 8)
        self.wLabel = QLabel(iConfigurationEditorWarning())
        self.tree = QTreeWidget(self)
        self.delegate = ConfigItemDelegate(self.tree)

        self.delegate.attributeChanged.connect(self.onAttrChanged)

        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(['Setting', 'Value', ''])
        self.tree.setHeaderHidden(True)
        self.tree.setItemDelegateForColumn(1, self.delegate)
        self.tree.itemDoubleClicked.connect(
            partialEnsure(self.onDoubleClick))
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tree.header().setStretchLastSection(False)
        self.addToLayout(self.wLabel)
        self.addToLayout(self.tree)
        self.setEnabled(False)

        ensureSafe(self.load())

    @property
    def root(self):
        return self.tree.invisibleRootItem()

    async def load(self):
        await self.loadSettings()
        self.setEnabled(True)

    async def loadSettings(self):
        self.tree.clear()

        bfont = self.font()
        bfont.setBold(True)
        bfont.setPointSize(16)

        for mod in configModules():
            modItem = ConfigModuleItem(self.root)
            modItem.setText(0, mod)
            modItem.setFont(0, bfont)

            await asyncio.sleep(0)

    def onAttrChanged(self, aIdx):
        item = self.tree.itemFromIndex(aIdx)
        if item:
            item.setText(self.COL_STATUS, 'OK')

            self.app.loop.call_later(
                2.0,
                item.setText,
                self.COL_STATUS,
                ''
            )

    async def onDoubleClick(self, modItem, col, *args):
        if not isinstance(modItem, ConfigModuleItem):
            return

        mod = modItem.text(0)

        if modItem.childCount() == 0:
            self.setEnabled(False)

            for attr in configModLeafAttributes(mod):
                value = cGet(attr, mod=mod)

                if isinstance(value, int) or isinstance(value, float):
                    item = QTreeWidgetItem(modItem)
                    item.setText(0, attr)
                    item.setText(1, str(value))

                    item.setData(1, ModRole, mod)
                    item.setData(1, AttrRole, attr)
                    item.setData(1, AttrTypeRole, type(value))

                    self.tree.openPersistentEditor(item, 1)

            modItem.setExpanded(True)
            self.setEnabled(True)
