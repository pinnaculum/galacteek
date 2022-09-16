import functools
import json

from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QTextBrowser
from PyQt5.QtWidgets import QWidget

from PyQt5.QtWidgets import QTableWidgetItem
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QHeaderView
from PyQt5.QtWidgets import QToolButton

from PyQt5.QtGui import QTextCursor
from PyQt5.QtGui import QFont
from PyQt5.QtGui import QBrush
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt

from galacteek import log

from galacteek.core import datetimeIsoH

from galacteek.core.ps import keyPsJson
from galacteek.core.ps import keyPsEncJson
from galacteek.core.ps import psSubscriber

from galacteek.ipfs.pubsub import TOPIC_CHAT
from galacteek.ipfs.pubsub import TOPIC_PEERS
from galacteek.ipfs.pubsub import TOPIC_LD_PRONTO

from .forms import ui_pubsubsniffer
from .helpers import getIcon
from .widgets import GalacteekTab


class PubsubSnifferWidget(GalacteekTab):
    MAX_MESSAGES_DEFAULT = 25

    def __init__(self, gWindow):
        super(PubsubSnifferWidget, self).__init__(gWindow)

        self.subscriber = psSubscriber('pubsub_sniffer')
        self.container = QWidget()
        self.vLayout.addWidget(self.container)

        self.ui = ui_pubsubsniffer.Ui_PubSubSniffer()
        self.ui.setupUi(self.container)

        for mm in range(5, 120, 5):
            self.ui.maxKeepMessages.addItem(str(mm))

        self.ui.maxKeepMessages.setCurrentText(
            str(PubsubSnifferWidget.MAX_MESSAGES_DEFAULT))

        self.ui.tableWidgetMsgs.setHorizontalHeaderLabels(
            ['Date', 'Topic', 'Sender', ''])
        self.ui.tableWidgetMsgs.setColumnCount(4)
        self.ui.tableWidgetMsgs.verticalHeader().hide()
        self.ui.tableWidgetMsgs.horizontalHeader().hide()
        self.ui.clearButton.clicked.connect(self.clearLog)

        horizHeader = self.ui.tableWidgetMsgs.horizontalHeader()
        horizHeader.setSectionResizeMode(QHeaderView.ResizeToContents)
        self.vLayout.addWidget(self.ui.tableWidgetMsgs)

        self.subscriber.add_async_listener(keyPsJson, self.onJsonMessage)
        self.subscriber.add_async_listener(keyPsEncJson, self.onJsonMessage)

    @property
    def maxMessages(self):
        return int(self.ui.maxKeepMessages.currentText())

    @property
    def topicFilter(self):
        return self.ui.topicFilter.currentText()

    @property
    def topicFilterCombo(self):
        return self.ui.topicFilter

    @property
    def topicsFound(self):
        return [self.topicFilterCombo.itemText(idx)
                for idx in range(0, self.topicFilterCombo.count())]

    async def unhookListeners(self):
        await self.subscriber.remove_listener(
            keyPsEncJson, self.onJsonMessage)
        await self.subscriber.remove_listener(
            keyPsJson, self.onJsonMessage)

    async def onJsonMessage(self, key, message):
        try:
            await self.processMessage(key, message)
        except RuntimeError:
            # Unhook PS listeners (we can catch this from .destroyed as well)
            await self.unhookListeners()
        except Exception as err:
            log.warning(f'Unable to process pubsub message: {err}')

    def clearLog(self, count=0):
        curc = self.ui.tableWidgetMsgs.rowCount()

        for ri in range(0, count if count > 0 else curc):
            self.ui.tableWidgetMsgs.removeRow(ri)

    async def processMessage(self, key, message):
        sender, topic, jsonMsg = message

        # Cleanup
        if self.ui.tableWidgetMsgs.rowCount() > self.maxMessages:
            self.clearLog(count=self.maxMessages)

        # Store topic in the topic filter combo
        if topic not in self.topicsFound:
            self.topicFilterCombo.addItem(topic)

        if self.topicFilter != '*' and topic != self.topicFilter:
            # Filter
            return

        dItem = QTableWidgetItem(datetimeIsoH())

        maxLen = 24
        if len(topic) > maxLen:
            tItem = QTableWidgetItem(topic[0:maxLen] + '...')
            tItem.setToolTip(topic)
        else:
            tItem = QTableWidgetItem(topic)

        sItem = QTableWidgetItem(sender)

        for item in [dItem, tItem, sItem]:
            item.setBackground(QBrush(QColor('#2b5278')))

            if key is keyPsEncJson:
                item.setBackground(QBrush(QColor(Qt.darkGray)))

            if topic == TOPIC_PEERS:
                item.setBackground(QBrush(QColor(Qt.darkGreen)))
            elif topic == TOPIC_CHAT:
                item.setBackground(QBrush(QColor('#2b5278')))
            elif topic == TOPIC_LD_PRONTO:
                item.setBackground(QBrush(QColor(Qt.red)))

        viewButton = QToolButton(self)
        viewButton.setIcon(getIcon('search-engine.png'))
        viewButton.clicked.connect(functools.partial(
            self.viewJsonMessage, jsonMsg))

        for item in [dItem, tItem, sItem]:
            item.setFlags(
                Qt.ItemIsSelectable | Qt.ItemIsEnabled)

        curRow = self.ui.tableWidgetMsgs.rowCount()
        self.ui.tableWidgetMsgs.insertRow(curRow)
        self.ui.tableWidgetMsgs.setItem(curRow, 0, dItem)
        self.ui.tableWidgetMsgs.setItem(curRow, 1, tItem)
        self.ui.tableWidgetMsgs.setItem(curRow, 2, sItem)
        self.ui.tableWidgetMsgs.setCellWidget(curRow, 3, viewButton)

    def viewJsonMessage(self, msgJson):
        """
        :param message bytes: raw message data
        """

        dlg = QDialog()
        layout = QVBoxLayout()
        dlg.setLayout(layout)
        dlg.setMinimumSize(
            (2 * self.app.desktopGeometry.width()) / 3,
            (2 * self.app.desktopGeometry.height()) / 3,
        )

        msgView = QTextBrowser(dlg)
        msgView.setFontFamily('Montserrat')
        msgView.setFontWeight(QFont.DemiBold)
        msgView.setFontPointSize(12)
        layout.addWidget(msgView)

        try:
            msgView.insertPlainText(
                json.dumps(msgJson, indent=4))
            msgView.moveCursor(QTextCursor.Start)
            dlg.exec_()
        except Exception:
            # TODO
            pass

    async def onClose(self):
        return True
