from . import SettingsFormController


class SettingsController(SettingsFormController):
    configModuleName = 'galacteek.services.net.bitmessage'

    async def settingsInit(self):
        self.cfgWatch(
            self.ui.enableBmService,
            'enabled',
            self.configModuleName
        )
        self.cfgWatch(
            self.ui.purgeOldObjectsOnStartup,
            'notbit.objects.purgeOlderThan.onStartup',
            self.configModuleName
        )
        self.cfgWatch(
            self.ui.notbitProcessNice,
            'notbit.process.nice',
            self.configModuleName
        )
