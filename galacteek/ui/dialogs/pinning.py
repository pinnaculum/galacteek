import validators

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QRegExp

from PyQt5.QtGui import QRegExpValidator

from galacteek.ui.dialogs import BaseDialog

from galacteek.ui.widgets import LabelWithURLOpener
from galacteek.ui.forms.ui_rps_adddialog import *
from galacteek.ui.i18n import iPinataInstructions


class PinningServiceAddDialog(BaseDialog):
    uiClass = Ui_PinningServiceAddDialog

    def dialogSetup(self):
        self.ui.endpoint.setEnabled(False)

        self.ui.buttonBox.accepted.connect(self.accept)
        self.ui.buttonBox.rejected.connect(self.reject)
        self.ui.endpointCustom.stateChanged.connect(
            lambda checked: self.ui.endpoint.setEnabled(checked))

        self.infoLabel = LabelWithURLOpener('')
        self.infoLabel.setObjectName('rpsPinataInstructions')

        self.ui.hLayoutInfo.addWidget(self.infoLabel, 0, Qt.AlignCenter)

        self.ui.name.setValidator(
            QRegExpValidator(QRegExp(r"[\w\-\_]{1,32}"))
        )

        self.ui.provider.currentTextChanged.connect(
            self.onProviderChanged)
        self.providerReact(self.ui.provider.currentText())

    def onProviderChanged(self, provName):
        self.providerReact(provName)

    def providerReact(self, provName: str):
        if provName == 'Pinata':
            self.ui.endpoint.setText(
                'https://api.pinata.cloud/psa'
            )

            self.infoLabel.setText(iPinataInstructions())
        elif provName == 'Other':
            self.ui.endpointCustom.setChecked(True)
            self.ui.endpoint.setText('')

    def getKey(self, inputKey: str):
        st = inputKey.strip().split('\n')

        if not st:
            return None

        for item in st:
            if item != '':
                return item

    def options(self):
        name = self.ui.name.text()
        endpoint = self.ui.endpoint.text()

        key = self.getKey(self.ui.secret.toPlainText())

        if not validators.url(endpoint):
            raise ValueError('Invalid endpoint URL')

        if not key:
            raise ValueError('Invalid key')

        return {
            'name': name,
            'provider': self.ui.provider.currentText(),
            'endpoint': endpoint,
            'secret': key
        }
