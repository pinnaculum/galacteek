from . import SettingsFormController


class SettingsController(SettingsFormController):
    configModuleName = 'galacteek.ui.files'
    qrcIcon = 'folder-open.png'

    async def settingsInit(self):
        self.cfgWatch(
            self.ui.mfsDirTooltips,
            'fileManager.mfsToolTips.showForDirectories',
            self.configModuleName
        )
        self.cfgWatch(
            self.ui.mfsFileTooltips,
            'fileManager.mfsToolTips.showForFiles',
            self.configModuleName
        )
