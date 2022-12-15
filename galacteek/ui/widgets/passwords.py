import functools

from yarl import URL

from PyQt5.QtCore import QPoint

from galacteek import AsyncSignal
from galacteek import ensure
from galacteek.core import runningApp
from galacteek.ipfs import ipfsOp


from ..helpers import easyToolTip
from ..helpers import inputPassword
from ..helpers import runDialogAsync
from ..dialogs import WebCredentialsStoreAskDialog

from ..i18n import iPasswordsVaultUnlock
from ..i18n import iPasswordsVaultOpened

from . import PopupToolButton


class PasswordsManager(PopupToolButton):
    pwStoreRequest = AsyncSignal(
        URL,
        URL,
        str,
        str,
        str,
        str
    )

    def __init__(self, *args, **kw):
        self.__store = kw.pop('credsStore', None)

        super(PasswordsManager, self).__init__(*args, **kw)

    def buttonPos(self):
        return self.mapToGlobal(QPoint(
            0,
            0
        ))

    def setupButton(self):
        self.actionUnlock = self.menu.addAction(
            iPasswordsVaultUnlock(),
            functools.partial(self.onUnlock)
        )
        self.pwStoreRequest.connectTo(self.onPwStore)

    def forUrl(self, actor: str, url: URL):
        for cred in self.__store.credentialsForUrl(url, subject=actor):
            yield cred

    async def onPwStore(self,
                        url: URL,
                        submitUrl: URL,
                        usernameField: str,
                        pwdField: str,
                        username: str,
                        password: str):
        app = runningApp()

        dlg = WebCredentialsStoreAskDialog()
        dlg.ui.siteUrl.setText(str(url))

        dlg.resize(
            app.desktopGeometry.width() * 0.3,
            app.desktopGeometry.height() * 0.2
        )

        dlg.move(QPoint(
            self.buttonPos().x() - dlg.width(),
            self.buttonPos().y() - dlg.height()
        ))

        await runDialogAsync(dlg)

        if dlg.result() == 1:
            self.__store.sc(
                url,
                submitUrl,
                username,
                password,
                usernameField=usernameField,
                passwordField=pwdField
            )

    def onUnlock(self):
        pwd = inputPassword()

        if not pwd:
            return

        ensure(self.__openVault(pwd))

    @ipfsOp
    async def __openVault(self, ipfsop, pwd: str):
        profile = ipfsop.ctx.currentProfile
        ipid = await profile.userInfo.ipIdentifier()

        if not ipid:
            return

        result = runningApp().pwVaultOpen(pwd)

        if result:
            # Allow the current DID read/write access to the vault
            self.__store.aclAllow(ipid.did, '/passwords/*', 'read')
            self.__store.aclAllow(ipid.did, '/passwords/*', 'write')

            easyToolTip(
                iPasswordsVaultOpened(),
                self.buttonPos(),
                self,
                4000
            )
