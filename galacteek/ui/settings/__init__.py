import functools
import importlib
import traceback

from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QListWidgetItem
from PyQt5.QtWidgets import QWidget

from PyQt5.QtWidgets import QFontComboBox
from PyQt5.QtWidgets import QComboBox
from PyQt5.QtWidgets import QCheckBox
from PyQt5.QtWidgets import QSpinBox
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QScrollArea

from PyQt5.QtCore import QObject
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QUrl
from PyQt5.QtCore import QItemSelectionModel

from galacteek.config import cGet
from galacteek.config import cSet
from galacteek.config import Configurable
from galacteek.core import runningApp
from galacteek.core.ps import KeyListener

from galacteek import ensure
from galacteek.appsettings import *

from galacteek.browser.schemes import SCHEME_IPFS
from galacteek.browser.schemes import SCHEME_ENS

from galacteek.ui.forms import ui_settings_center

from ..widgets import GalacteekTab
from ..forms import ui_settings
from ..themes import themesList

from ..helpers import *
from ..i18n import *


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

        if 0:
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


SettingsModNameRole = Qt.UserRole + 1
SettingsModWidgetRole = Qt.UserRole + 2
SettingsModControllerRole = Qt.UserRole + 3


class SettingsCenterTab(GalacteekTab,
                        KeyListener):
    modules = {}

    def tabSetup(self):
        widget = QWidget()

        self.ui = ui_settings_center.Ui_SettingsCenter()
        self.ui.setupUi(widget)

        self.ui.sModules.itemClicked.connect(self.onModuleClicked)
        self.ui.sModules.currentItemChanged.connect(self.onModuleChanged)
        self.addToLayout(widget)

    def selectConfigModule(self, mod: str):
        modItem = self.modules.get(mod)
        if modItem:
            self.ui.sModules.setCurrentItem(
                modItem,
                QItemSelectionModel.SelectCurrent
            )

    def loadModules(self):
        self.load('General', 'general')
        self.load('IPFS', 'ipfs')
        self.load('Browser', 'browser')
        self.load('User Interface', 'ui')
        self.load('Ethereum', 'ethereum')
        self.load('Files', 'files')
        self.load(iRemotePinning(), 'pinning')
        self.load(iBitMessage(), 'bitmessage')

        for pName, profile in self.app.webProfiles.items():
            self.load(
                iWebProfileLabel(pName),
                'webprofile',
                webProfileName=pName,
                webProfile=profile
            )

        for scheme in [SCHEME_IPFS, SCHEME_ENS]:
            self.load(f'URL Scheme: {scheme}',
                      'urlscheme',
                      schemeName=scheme)

    async def event_g_services_app(self, key, message):
        event = message['event']

        if event['type'] == 'ApplicationServiceReady':
            self.loadModules()

    def resizeEvent(self, event):
        self.ui.sModules.setFixedWidth(0.25 * event.size().width())

    def onModuleClicked(self, item):
        widget = item.data(SettingsModWidgetRole)
        if widget:
            self.ui.stack.setCurrentWidget(widget)

    def onModuleChanged(self, currentItem, oldItem) -> None:
        widget = currentItem.data(SettingsModWidgetRole)
        if widget:
            self.ui.stack.setCurrentWidget(widget)

    def load(self, displayName: str, modname: str,
             **data):
        try:
            uiFormModule = importlib.import_module(
                f'galacteek.ui.forms.ui_settings_{modname}')
            ctrlMod = importlib.import_module(
                f'galacteek.ui.settings.{modname}')

            form = uiFormModule.Ui_SettingsForm()

            widget = QWidget()
            widget.ui = form
            form.setupUi(widget)

            controller = ctrlMod.SettingsController(widget,
                                                    parent=self.ui.stack,
                                                    **data)
            controller._map()

            # settingsInit() ought to be a regular function really..
            ensure(controller.settingsInit())
        except Exception:
            traceback.print_exc()
        else:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(widget)
            scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

            self.ui.stack.addWidget(scroll)

            item = QListWidgetItem(displayName)
            item.setData(SettingsModWidgetRole, scroll)
            item.setData(SettingsModNameRole, modname)
            item.setData(SettingsModControllerRole, controller)

            item.setIcon(getIcon(controller.qrcIcon))

            self.ui.sModules.addItem(item)
            self.modules[modname] = item

            if not self.ui.sModules.currentItem():
                self.ui.sModules.setCurrentItem(
                    item,
                    QItemSelectionModel.SelectCurrent
                )
                self.ui.stack.setCurrentWidget(scroll)


class SettingsBaseController(QObject, Configurable, KeyListener):
    def cfgValueTranslate(self, cAttr, value):
        pass

    def cfgWatch(self, widget, cAttr, cMod):
        def valueChanged(value, attr, mod):
            cSet(attr, value, mod=mod)

        val = cGet(cAttr, mod=cMod)

        if isinstance(widget, QComboBox):
            def comboTextChanged(text: str):
                data = widget.itemData(widget.currentIndex())

                if isinstance(data, str):
                    valueChanged(data, cAttr, cMod)
                else:
                    valueChanged(text, cAttr, cMod)

            widget.currentTextChanged.connect(
                functools.partial(comboTextChanged)
            )

            widget.setCurrentText(str(val))
        elif isinstance(widget, QFontComboBox):
            widget.currentFontChanged.connect(
                lambda font: valueChanged(font.family(), cAttr, cMod)
            )
            widget.setCurrentText(str(val))

        elif isinstance(widget, QSpinBox):
            widget.valueChanged.connect(
                lambda value: valueChanged(value, cAttr, cMod)
            )
            widget.setValue(val)
        elif isinstance(widget, QCheckBox):
            widget.stateChanged.connect(
                lambda state: valueChanged(
                    state == Qt.Checked, cAttr, cMod)
            )
            widget.setChecked(val)
        elif isinstance(widget, QLineEdit):
            widget.textChanged.connect(
                lambda text: valueChanged(text, cAttr, cMod)
            )
            widget.setText(val)


class SettingsFormController(SettingsBaseController):
    qrcIcon: str = 'settings.png'

    def __init__(self, sWidget, parent=None, **extra):
        super().__init__(sWidget)

        self.app = runningApp()
        self.sWidget = sWidget
        self.extra = extra
        self.prepare()

    @property
    def mapping(self) -> dict:
        return {}

    def prepare(self) -> None:
        pass

    def _map(self) -> None:
        for cfgmod, cfg in self.mapping.items():
            for mcfg in cfg:
                try:
                    if isinstance(mcfg, tuple):
                        # First element in the tuple  is the attribute name
                        # Second element in tuple is the UI object's name
                        self.cfgWatch(
                            getattr(self.ui, mcfg[1]),
                            mcfg[0],
                            cfgmod
                        )
                    elif isinstance(mcfg, str):
                        self.cfgWatch(
                            getattr(self.ui, mcfg.split('.')[-1]),
                            mcfg,
                            cfgmod
                        )
                except Exception:
                    traceback.print_exc()
                    continue

    async def settingsInit(self) -> None:
        pass

    @property
    def ui(self):
        return self.sWidget.ui
