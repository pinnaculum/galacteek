import traceback

from PyQt5.QtCore import Qt

from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QTextEdit

from PyQt5.QtGui import QKeySequence

from galacteek import ensure
from galacteek.ai import openai as opai

from ..widgets import GalacteekTab
from ..forms import ui_openai_discussion


class ChatBotSessionTab(GalacteekTab):
    def __init__(self, mainW):
        super().__init__(mainW)

        self.sessionWidget = QWidget(self)

        self.ui = ui_openai_discussion.Ui_Form()
        self.ui.setupUi(self.sessionWidget)

        self.ui.askButton.clicked.connect(self.onAsk)
        self.ui.askButton.setShortcut(QKeySequence('Ctrl+Return'))

        self.addToLayout(self.sessionWidget)

        self.ui.prompt.setFocus(Qt.OtherFocusReason)

    def resizeEvent(self, event):
        self.ui.prompt.setMaximumHeight(event.size().width() / 8)

    def onAsk(self):
        text = self.ui.prompt.toPlainText()

        if text:
            ensure(self.runCompletion(text))

    async def runCompletion(self, prompt: str):
        try:
            comp = await opai.complete(prompt)
        except Exception:
            traceback.print_exc()
        else:
            tedit = QTextEdit()
            tedit.append(comp.choices[0].text)

            self.ui.vLayoutChat.insertWidget(
                self.ui.vLayoutChat.count(),
                tedit
            )
