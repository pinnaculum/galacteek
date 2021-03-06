import validators

from PyQt5.QtCore import Qt

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
        self.ui.hLayoutInfo.addWidget(self.infoLabel, 0, Qt.AlignCenter)

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

    def options(self):
        try:
            name = self.ui.name.text()
            endpoint = self.ui.endpoint.text()
            key = self.ui.secret.toPlainText().strip()

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

        except Exception:
            return None
