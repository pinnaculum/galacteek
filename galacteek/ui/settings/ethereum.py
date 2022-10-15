import re

from galacteek.core import runningApp

from . import SettingsFormController


class SettingsController(SettingsFormController):
    configModuleName = 'galacteek.services.dweb.ethereum'
    qrcIcon = 'ethereum.png'

    @property
    def mapping(self):
        return {
            'galacteek.services.dweb.ethereum': [
                ('infura.projectId', 'infuraId'),
                ('infura.projectSecret', 'infuraSecret')
            ]
        }

    def onIdChange(self, text: str) -> None:
        if re.search(r'[a-zA-Z0-9]{32,64}', text):
            self.ui.infuraId.setProperty('inputvalid', True)
        else:
            self.ui.infuraId.setProperty('inputvalid', False)

        runningApp().repolishWidget(self.ui.infuraId)

    async def settingsInit(self):
        self.ui.infuraId.textEdited.connect(self.onIdChange)
