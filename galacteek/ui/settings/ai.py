from PyQt5.QtGui import QPixmap

from galacteek import ensure
from galacteek.ai import openai as openai_api

from . import SettingsFormController


class SettingsController(SettingsFormController):
    configModuleName = 'galacteek.ai.openai'

    @property
    def mapping(self):
        return {
            'galacteek.ai.openai': [
                ('accounts.main.apiKey', 'openaiApiKey')
            ]
        }

    def prepare(self):
        self.ui.testAccountButton.clicked.connect(self.onTest)
        self.ui.testAccountButton.setEnabled(False)

    def cfgItemChanged(self, widget, mod: str, attr: str, value: str):
        if attr == 'accounts.main.apiKey':
            self.ui.testAccountButton.setEnabled(False)

            # Basic validation
            if value and openai_api.apiKeyValid(value):
                self.reconfigureOpenAi(value)
                self.ui.testAccountButton.setEnabled(True)
            else:
                openai_api.resetApiKey()

    def reconfigureOpenAi(self, apiKey: str):
        openai_api.reconfigure(apiKey=apiKey)

    def onTest(self):
        ensure(self.testAccount())

    async def testAccount(self):
        try:
            comp = await openai_api.complete('How are you doing ?')
            assert comp is not None

            answer = comp.choices[0].text

            if answer:
                self.ui.testAccountResult.setPixmap(
                    QPixmap(':/share/icons/ai/chatbot.png')
                )
            else:
                raise ValueError('No reply')
        except Exception:
            self.ui.testAccountResult.setPixmap(
                QPixmap(':/share/icons/cancel.png')
            )
