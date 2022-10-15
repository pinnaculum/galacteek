from PyQt5.QtCore import Qt

from . import SettingsFormController

from galacteek.ui.i18n import iUrlSchemeLabel


class SettingsController(SettingsFormController):
    configModuleName = 'galacteek.browser.schemes'
    qrcIcon = 'network.png'

    @property
    def schemeName(self):
        return self.extra['schemeName']

    @property
    def mapping(self):
        return {
            self.configModuleName: [
                f'byScheme.{self.schemeName}.chunkReadTimeout',
                f'byScheme.{self.schemeName}.chunkSizeDefault',
                f'byScheme.{self.schemeName}.contentCacheEnable',
                f'byScheme.{self.schemeName}.contentCacheMaxObjectSize'
            ]
        }

    def onCacheChange(self, state: int) -> None:
        for wid in [self.ui.contentCacheMaxObjectSize]:
            wid.setEnabled(state == Qt.Checked)

    def prepare(self):
        self.ui.contentCacheEnable.stateChanged.connect(self.onCacheChange)

    async def settingsInit(self):
        self.ui.groupBoxMain.setTitle(iUrlSchemeLabel(self.schemeName))
