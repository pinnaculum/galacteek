import asyncio
import base64
import functools
import os
import traceback

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QSize
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import pyqtSlot

from PyQt5.QtGui import QPixmap
from PyQt5.QtGui import QFont
from PyQt5.QtGui import QFontMetrics

from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QTextEdit
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QToolButton
from PyQt5.QtWidgets import QSpacerItem
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QMenu
from PyQt5.QtQuickWidgets import QQuickWidget

from galacteek import ensure
from galacteek.ai import openai as opai
from galacteek.core import runningApp
from galacteek.core.tmpf import TmpFile
from galacteek.core.asynclib import asyncWriteFile
from galacteek.core.langtags import mainLangTags
from galacteek.qml import quickWidgetFromFile

from ..helpers import getIcon
from ..widgets import GalacteekTab
from ..widgets import AnimatedLabel
from ..clips import BouncyOrbitClip
from ..forms import ui_openai_discussion
from ..notify import uiNotify
from ..i18n import iChatBotGenerateOneImage
from ..i18n import iChatBotGenerateImageCount
from ..i18n import iChatBotTranslateToLang
from ..i18n import iChatBotInvalidResponse


def stripEmpty(s: str) -> str:
    lines = s.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    return '\n'.join(lines)


gptTsLangs: list = [
    'Albanian',
    'Arabic',
    'Armenian',
    'Awadhi',
    'Azerbaijani',
    'Bashkir',
    'Basque',
    'Belarusian',
    'Bengali',
    'Bosnian',
    'Brazilian Portuguese',
    'Bulgarian',
    'Catalan',
    'Chinese',
    'Croatian',
    'Czech',
    'Danish',
    'Dogri',
    'Dutch',
    'English',
    'Estonian',
    'Faroese',
    'Finnish',
    'French',
    'Galician',
    'Georgian',
    'German',
    'Greek',
    'Hindi',
    'Hungarian',
    'Indonesian',
    'Irish',
    'Italian',
    'Japanese',
    'Javanese',
    'Kashmiri',
    'Kazakh',
    'Korean',
    'Latvian',
    'Lithuanian',
    'Macedonian',
    'Maltese',
    'Mandarin',
    'Mandarin Chinese',
    'Moldovan',
    'Mongolian',
    'Montenegrin',
    'Nepali',
    'Norwegian',
    'Persian (Farsi)',
    'Polish',
    'Portuguese',
    'Punjabi',
    'Rajasthani',
    'Romanian',
    'Russian',
    'Sanskrit',
    'Serbian',
    'Slovak',
    'Slovene',
    'Slovenian',
    'Spanish',
    'Swahili',
    'Swedish',
    'Thai',
    'Turkish',
    'Turkmen',
    'Ukrainian',
    'Uzbek',
    'Vietnamese',
    'Welsh'
]


class ChatBotDiscussionWidget(QWidget):
    """
    The discussions container widget that lives inside the scroll area
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.vl = QVBoxLayout()
        self.vls = QVBoxLayout()
        self.setLayout(self.vl)

        self.chatWLabel = QLabel(self)
        self.chatWLabel.setPixmap(
            QPixmap(':/share/img/chatbot-blue.jpg')
        )

        self.vl.addWidget(self.chatWLabel, 0, Qt.AlignCenter)
        self.spacer = None

    @property
    def wcount(self):
        return self.vl.count()

    def adjustImage(self):
        self.chatWLabel.setPixmap(
            QPixmap(':/share/img/chatbot-blue.jpg').scaledToHeight(
                self.size().height() * 0.8)
        )

    def onRemoveQuestion(self, qaw):
        qaw.setParent(None)
        self.vl.removeWidget(qaw)

    def go(self, prompt: str):
        self.chatWLabel.hide()

        qa = QuestionAnswer(prompt,
                            parent=self)

        qa.rmRequested.connect(functools.partial(self.onRemoveQuestion,
                                                 qa))

        self.vl.insertWidget(self.vl.count(), qa)

        if not self.spacer:
            # Add a spacer item in the spacer layout
            self.spacer = QSpacerItem(10, 10,
                                      QSizePolicy.Expanding,
                                      QSizePolicy.Expanding)
            self.vls.addSpacerItem(self.spacer)
            self.vl.addLayout(self.vls)

        uiNotify('chatBotAsking')

        return qa


class QuestionAnswer(QWidget):
    """
    Widget representing a question and answer in the context of a
    chatbot discussion
    """

    rmRequested = pyqtSignal()

    def __init__(self, question: str, parent=None):
        super().__init__(parent)

        self.vl = QVBoxLayout()
        self.setLayout(self.vl)

        ql = QHBoxLayout()

        qi = QLabel()
        qi.setPixmap(
            QPixmap(':/share/icons/question.png').scaledToWidth(32))

        font = QFont('Times', 14)
        font.setBold(True)
        fm = QFontMetrics(font)

        rmButton = QToolButton()
        rmButton.setIcon(getIcon('cancel.png'))
        rmButton.clicked.connect(self.rmRequested.emit)

        self.cbButton = QToolButton()
        self.cbButton.setIcon(getIcon('clipboard.png'))
        self.cbButton.clicked.connect(self.copyToClipboard)
        self.cbButton.setEnabled(False)

        # Question label
        qLabel = QLabel(f'<b>{question}</b>')
        qLabel.setFont(font)
        qLabel.setToolTip(question)
        qLabel.setAlignment(Qt.AlignLeft)
        qLabel.setMaximumHeight(fm.lineSpacing() * 3)

        ql.addWidget(rmButton)
        ql.addWidget(self.cbButton)
        ql.addWidget(qi)
        ql.addWidget(qLabel)

        self.vl.addLayout(ql)

        self.answerLayout = QVBoxLayout()

        self.anim = AnimatedLabel(BouncyOrbitClip())
        self.anim.startClip()
        self.anim.clip.setScaledSize(QSize(256, 256))

        self.answerLayout.addWidget(self.anim, 0, Qt.AlignCenter)

        self.vl.addLayout(self.answerLayout)

    def rmAnim(self):
        self.anim.setParent(None)
        self.answerLayout.removeWidget(self.anim)

    def copyToClipboard(self):
        for iti in range(0, self.answerLayout.count()):
            item = self.answerLayout.itemAt(iti)
            widget = item.widget()

            if widget and isinstance(widget, QTextEdit):
                runningApp().setClipboardText(
                    widget.toPlainText()
                )

    def showTextCompletion(self, answer: str,
                           maxLines: int = 100) -> None:
        self.rmAnim()

        answerText = QTextEdit()
        answerText.setViewportMargins(6, 6, 6, 6)
        answerText.setReadOnly(True)
        answerText.setPlainText(stripEmpty(answer))

        fm = QFontMetrics(answerText.font())

        answerText.setMinimumHeight(fm.lineSpacing() * 40)

        answerText.setFixedHeight(
            min(max(8, answerText.document().lineCount()),
                maxLines) * fm.lineSpacing()
        )

        self.answerLayout.addWidget(answerText)
        self.cbButton.setEnabled(True)

    def showImage(self, imgData):
        self.rmAnim()

        try:
            pix = QPixmap()
            pix.loadFromData(imgData)

            imgLabel = QLabel()
            imgLabel.setPixmap(pix)

            self.answerLayout.addWidget(imgLabel)
        except Exception:
            traceback.print_exc()

    def showQmlProgram(self, qmlWidget):
        self.rmAnim()

        self.answerLayout.addWidget(qmlWidget)

    def error(self, err: str):
        self.rmAnim()

        errLabel = QLabel(f'Error: {err}')
        errLabel.setToolTip(err)
        errLabel.setAlignment(Qt.AlignLeft)

        self.answerLayout.addWidget(errLabel)


class ChatBotSessionTab(GalacteekTab):
    """
    ChatBot discussion tab
    """

    def __init__(self, mainW):
        super().__init__(mainW)

        self.sessionWidget = QWidget(self)
        self.disc = ChatBotDiscussionWidget(parent=self)

        self.ui = ui_openai_discussion.Ui_Form()
        self.ui.setupUi(self.sessionWidget)
        self.addToLayout(self.sessionWidget)

        self.ui.prompt.setViewportMargins(10, 10, 10, 10)

        self.ui.askButton.clicked.connect(self.onAsk)

        self.ui.qmlGenButton.clicked.connect(self.onQmlGen)
        self.ui.clearChat.clicked.connect(self.onClearChat)

        self.ui.imageGenButton.setPopupMode(QToolButton.InstantPopup)

        self.tsLangMenu = QMenu()
        self.tsLangMenu.triggered.connect(self.onTranslate)
        self.imageGenMenu = QMenu()
        self.setupTsLangMenu()

        for x in range(1, 15):
            self.imageGenMenu.addAction(
                iChatBotGenerateOneImage() if x == 1 else
                iChatBotGenerateImageCount(x),
                functools.partial(self.onImageGen, x)
            )

            if x == 1:
                self.imageGenMenu.addSeparator()

        self.ui.imageGenButton.setMenu(self.imageGenMenu)

        self.ui.tsButton.setMenu(self.tsLangMenu)

        self.ui.scrollArea.setWidget(self.disc)
        self.ui.scrollArea.setViewportMargins(2, 2, 2, 2)

        self.vscrollbar = self.ui.scrollArea.verticalScrollBar()
        self.vscrollbar.rangeChanged.connect(self.scrollToBottomIfNeeded)
        self.vscrollbar.valueChanged.connect(self.storeAtBottomState)

        self.atBottom = False

        self.app.loop.call_later(0.05, self.ui.prompt.setFocus)

    @pyqtSlot(int)
    def storeAtBottomState(self, value):
        self.atBottom = value == self.vscrollbar.maximum()

    @pyqtSlot(int, int)
    def scrollToBottomIfNeeded(self, minimum, maximum):
        if maximum > 0:
            self.vscrollbar.setValue(maximum)

    def keyPressEvent(self, event):
        modifiers = event.modifiers()

        if modifiers & Qt.ControlModifier:
            if event.key() == Qt.Key_L:
                self.app.loop.call_later(0.05, self.ui.prompt.setFocus)

        super(ChatBotSessionTab, self).keyPressEvent(event)

    def setupTsLangMenu(self):
        for tag, name in mainLangTags().items():
            if name not in gptTsLangs:
                continue

            action = self.tsLangMenu.addAction(
                iChatBotTranslateToLang(name)
            )
            action.setData(name)

    def evis(self, widget, x: int = 0, y: int = 0) -> None:
        """
        Ensures that a widget is visible in the scroll area
        """

        self.ui.scrollArea.ensureWidgetVisible(widget, x, y)

    def resizeEvent(self, event) -> None:
        self.disc.adjustImage()

    def onClearChat(self) -> None:
        self.disc = ChatBotDiscussionWidget(parent=self)
        self.ui.scrollArea.setWidget(self.disc)
        self.disc.adjustImage()

    def prompt(self) -> str:
        text = self.ui.prompt.toPlainText()

        if text:
            self.ui.prompt.clear()
            return text

    def onAsk(self) -> None:
        text = self.prompt()

        if text:
            ensure(self.runCompletion(text))

    def onImageGen(self, count: int):
        text = self.prompt()

        if text:
            ensure(self.imageGenerate(text, count))

    def onQmlGen(self):
        text = self.prompt()

        if text:
            ensure(self.qmlGenerate(text))

    def onTranslate(self, action) -> None:
        lang = action.data()
        text = self.prompt()

        if text and lang:
            ensure(self.runCompletion(f'Translate "{text}" to {lang}'))

    async def runCompletion(self, prompt: str):
        qa = self.disc.go(prompt)

        try:
            resp = await opai.complete(prompt)
            assert len(resp.choices) > 0
        except AssertionError:
            qa.error(iChatBotInvalidResponse())
        except Exception as err:
            qa.error(str(err))
        else:
            for comp in resp.choices:
                qa.showTextCompletion(comp.text)

        uiNotify('chatBotGotAnswer')

    async def imageGenerate(self, prompt: str, count: int) -> None:
        qa = self.disc.go(prompt)

        try:
            response = await opai.image(prompt,
                                        n=count)
            assert response
        except AssertionError:
            qa.error(iChatBotInvalidResponse())
        except Exception as err:
            qa.error(str(err))
        else:
            for data in response['data']:
                img = base64.b64decode(data['b64_json'])

                qa.showImage(img)

                await asyncio.sleep(0.05)

            uiNotify('chatBotGotAnswer')

    async def qmlGenerate(self, prompt: str):
        qa = self.disc.go(prompt)

        try:
            comp = await opai.complete(prompt)

            assert comp
            assert len(comp.choices) > 0
        except AssertionError:
            qa.error(iChatBotInvalidResponse())
        except Exception as err:
            qa.error(str(err))
        else:
            code = comp.choices[0].text

            with TmpFile(suffix='.qml', delete=False) as file:
                await asyncWriteFile(file.name,
                                     code, 'wt')

            qa.showTextCompletion(code)

            qmlw = quickWidgetFromFile(file.name,
                                       parent=qa,
                                       show=False)

            os.remove(file.name)

            status = qmlw.status()

            if status == QQuickWidget.Ready:
                qmlw.setMinimumSize(QSize(
                    self.disc.width() * 0.8,
                    self.ui.scrollArea.height() * 0.5
                ))
                qmlw.setMinimumSize(QSize(
                    self.disc.width() * 0.9,
                    self.ui.scrollArea.height() * 0.7
                ))

                qa.showQmlProgram(qmlw)
                qa.show()

                uiNotify('chatBotGotAnswer')
            elif status == QQuickWidget.Error:
                errors = '\n'.join([e.toString() for e in qmlw.errors()])

                qa.error(f'QML Error: {errors}')
