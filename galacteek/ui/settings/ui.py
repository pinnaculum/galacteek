from galacteek.config import cGet

from . import SettingsFormController

from ..helpers import langTagComboBoxInit
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

            self.ui.uiLangTag.addItem(
                langDisplayName,
                langCode
            )

        for idx in range(self.ui.uiLangTag.count()):
            code = self.ui.uiLangTag.itemData(idx)
            if code == langCodeCurrent:
                self.ui.uiLangTag.setCurrentIndex(idx)

        langTagComboBoxInit(self.ui.contentLangTag)

        # Theme
        self.ui.themeCombo.clear()

        for themeName, tPath in themesList():
            self.ui.themeCombo.addItem(themeName)

        self.cfgWatch(
            self.ui.uiLangTag,
            'language',
            'galacteek.application'
        )

        self.cfgWatch(
            self.ui.contentLangTag,
            'defaultContentLanguage',
            'galacteek.application'
        )

        self.cfgWatch(
            self.ui.themeCombo,
            'theme',
            'galacteek.ui'
        )
        self.cfgWatch(
            self.ui.toolbarsIconSize,
            'styles.galacteek.desktopGeneric.metrics.toolBarIconSize',
            'galacteek.ui'
        )

        self.ui.themeCombo.currentTextChanged.connect(
            self.applyTheme
        )

    def applyTheme(self, themeName: str):
        self.app.themes.change(themeName)
