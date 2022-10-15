from . import SettingsFormController


class SettingsController(SettingsFormController):
    configModuleName = 'galacteek.browser.webprofiles'
    qrcIcon = 'ipfs-logo-128-white.png'

    # Main profile settings
    coreSettings = [
        'cacheType',
        'cacheMaxSizeMb',
        'cookiesPolicy',
        'defaultFontSize',
        'minFontSize',
        'offTheRecord',
        'pdfViewerInternal'
    ]

    @property
    def profile(self):
        return self.extra['webProfile']

    @property
    def profileName(self):
        return self.extra['webProfileName']

    def sWatch(self, uiel, attr):
        self.cfgWatch(
            uiel,
            f'webProfiles.{self.profileName}.settings.{attr}',
            self.configModuleName
        )

    def fontWatch(self, uiel, attr):
        self.cfgWatch(
            uiel,
            f'webProfiles.{self.profileName}.fonts.{attr}',
            self.configModuleName
        )

    async def settingsInit(self):
        for setting in self.coreSettings:
            self.sWatch(
                getattr(self.ui, setting),
                setting
            )

        self.sWatch(
            self.ui.javascriptEnabled,
            'javascript.enabled'
        )

        self.sWatch(
            self.ui.javascriptCanOpenWindows,
            'javascript.canOpenWindows'
        )

        self.sWatch(
            self.ui.javascriptCanAccessClipboard,
            'javascript.canAccessClipboard'
        )

        self.fontWatch(
            self.ui.fontStandard,
            'standard'
        )
        self.fontWatch(
            self.ui.fontFixed,
            'fixed'
        )
        self.fontWatch(
            self.ui.fontSerif,
            'serif'
        )
        self.fontWatch(
            self.ui.fontSansSerif,
            'sansSerif'
        )
