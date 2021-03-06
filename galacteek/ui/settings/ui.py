
from galacteek.config import cGet

from . import SettingsBaseController

from ..themes import themesList


class SettingsController(SettingsBaseController):
    configModuleName = 'galacteek.ui'

    def __init__(self, sWidget, parent=None):
        super().__init__(sWidget, parent=parent)

    async def event_g_services_app(self, key, message):
        pass

    async def settingsInit(self):
        # self.cApply()

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
        self.ui.urlHistoryEnable.setChecked(
            cGet('enabled', mod='galacteek.ui.history'))

        # UI
        self.ui.webEngineDefaultZoom.setValue(
            cGet('zoom.default', mod='galacteek.ui.browser'))
