from PyQt5.QtCore import QRegExp
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QUrl

from PyQt5.QtGui import QRegExpValidator

from galacteek.browser.schemes import isUrlSupported
from galacteek.ld.rdf import tags as rdf_tags

from . import BaseDialog
from ..helpers import langTagComboBoxInit
from ..helpers import langTagComboBoxGetTag
from ..helpers import messageBoxAsync
from ..forms import ui_createtagdialog


class CreateTagDialog(BaseDialog):
    uiClass = ui_createtagdialog.Ui_CreateTagDialog

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.ui.buttonBox.accepted.connect(self.accept)
        self.ui.buttonBox.rejected.connect(self.reject)

        self.ui.setTagPriority.stateChanged.connect(self.onSetPriorityChanged)

        self.ui.tagUriName.textEdited.connect(self.onUriEdited)
        self.ui.tagUriName.setValidator(
            QRegExpValidator(QRegExp(r'[\w-_:]{1,64}'))
        )
        self.ui.tagUriName.setFocus(Qt.OtherFocusReason)

        self.ui.setTagPriority.setChecked(False)

        langTagComboBoxInit(self.ui.tagMainLanguage)

    @property
    def watchTagChecked(self):
        return self.ui.watchTag.isChecked()

    @property
    def tagUri(self):
        uriName = self.ui.tagUriName.text()

        if uriName.startswith('it:'):
            uriName = uriName.replace('it:', '')

        return f'it:{uriName}'

    @property
    def prioritySpecified(self):
        return self.ui.setTagPriority.isChecked()

    def onSetPriorityChanged(self, state: int):
        self.ui.priority.setEnabled(state == Qt.Checked)

    def onUriEdited(self, text):
        if text:
            self.ui.tagUriLabel.setText(f'URI: <b>{self.tagUri}</b>')
        else:
            self.ui.tagUriLabel.setText('No URI given')

    async def create(self):
        langTag = langTagComboBoxGetTag(self.ui.tagMainLanguage)
        meanings = []
        uriName = self.ui.tagUriName.text()
        displayName = self.ui.displayName.text()
        meaningUrl = QUrl(self.ui.meaningUrl.text())

        if not uriName or not displayName:
            await messageBoxAsync('Invalid')

        if isUrlSupported(meaningUrl) and meaningUrl.isValid():
            meanings.append({
                '@context': 'ips://galacteek.ld/Tag',
                '@type': 'TagMeaning',
                'uri': meaningUrl.toString()
            })

        prio = self.ui.priority.value() if self.prioritySpecified else None

        try:
            assert await rdf_tags.tagCreate(
                self.tagUri,
                tagNames={
                    langTag: uriName
                },
                tagDisplayNames={
                    langTag: displayName
                },
                meanings=meanings,
                shortDescription={
                    langTag: self.ui.shortDescription.toPlainText()
                },
                watch=self.ui.watchTag.isChecked(),
                priority=prio
            ) is True
        except Exception as err:
            await messageBoxAsync(err)
