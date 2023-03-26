from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import QObject
from PyQt5.QtCore import QJsonValue

from yarl import URL

from galacteek import ensure
from galacteek.core import runningApp
from galacteek.browser.schemes import SCHEME_HTTPS
from galacteek.browser.schemes import SCHEME_IPFS
from galacteek.browser.schemes import SCHEME_IPNS


class DOMBridge(QObject):
    """
    DOM bridge
    """

    @pyqtSlot(str, str, str, str, str, str, QJsonValue)
    def onPasswordFormSubmitted(self,
                                locationUrl: str,
                                formSubmitUrl: str,
                                usernameFieldName: str,
                                passwordFieldName: str,
                                username: str,
                                password: str,
                                formData: QJsonValue):
        """
        Slot called by the form observer when a form
        with passwords is submitted.
        """

        try:
            url = URL(locationUrl)

            assert url.scheme in [
                SCHEME_HTTPS,
                SCHEME_IPFS,
                SCHEME_IPNS
            ]
        except Exception:
            return

        ensure(runningApp().credsManager.pwStoreRequest.emit(
            url,
            URL(formSubmitUrl),
            usernameFieldName,
            passwordFieldName,
            username,
            password
        ))
