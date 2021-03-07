
from galacteek.config import cGet

from . import SettingsFormController

from ..themes import themesList


class SettingsController(SettingsFormController):
    configModuleName = 'galacteek.ui'

    async def settingsInit(self):
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

        pNameList = self.app.availableWebProfilesNames()

        for pName in pNameList:
            self.ui.comboDefaultWebProfile.insertItem(
                self.ui.comboDefaultWebProfile.count(),
                pName
            )
        self.cfgWatch(
            self.ui.language,
            'language',
            'galacteek.application'
        )
        self.cfgWatch(
            self.ui.comboDefaultWebProfile,
            'defaultWebProfile',
            'galacteek.browser.webprofiles'
        )
        self.cfgWatch(
            self.ui.webEngineDefaultZoom,
            'zoom.default',
            'galacteek.ui.browser'
        )
        self.cfgWatch(
            self.ui.themeCombo,
            'theme',
            'galacteek.ui'
        )
        self.cfgWatch(
            self.ui.urlHistoryEnable,
            'enabled',
            'galacteek.ui.history'
        )

        self.ui.themeCombo.currentTextChanged.connect(
            self.applyTheme
        )

    def applyTheme(self, themeName: str):
        self.app.themes.change(themeName)
