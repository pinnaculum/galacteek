from yarl import URL

from PyQt5.QtCore import QPoint
from PyQt5.QtWidgets import QPushButton

from galacteek import AsyncSignal
from galacteek import ensure
from galacteek.core import runningApp
from galacteek.ipfs import ipfsOp

from ..helpers import getIcon
from ..helpers import easyToolTip
from ..helpers import inputPassword
from ..helpers import runDialogAsync

from ..dialogs import WebCredentialsStoreAskDialog
from ..dialogs import WebCredentialsCreateDialog

from ..i18n import iPasswordsVaultCreate
from ..i18n import iPasswordsVaultUnlock
from ..i18n import iPasswordsVaultUnlocked
from ..i18n import iPasswordsVaultOpened
from ..i18n import iPasswordsVaultOpenFailed


class PasswordsManager(QPushButton):
    def __init__(self, credsStore, parent=None):
        super(PasswordsManager, self).__init__(parent)

        self.__store = credsStore
        self.__unlocked = False

        self.pwStoreRequest = AsyncSignal(
            URL,
            URL,
            str,
            str,
            str,
            str
        )

        self.pwStoreRequest.connectTo(self.onPwStore)
        self.clicked.connect(self.unlock)

        self.updateButton()

    def buttonPos(self):
        return self.mapToGlobal(QPoint(
            0,
            0
        ))

    def updateButton(self, unlocked: bool = False):
        if not runningApp().pwVaultExists():
            self.setIcon(getIcon('vault-closed.png'))
            self.setToolTip(iPasswordsVaultCreate())
        elif unlocked or self.__unlocked:
            self.setIcon(getIcon('vault.png'))
            self.setToolTip(iPasswordsVaultUnlocked())
        else:
            self.setIcon(getIcon('vault-closed.png'))
            self.setToolTip(iPasswordsVaultUnlock())

        self.__unlocked = unlocked

    def forUrl(self, actor: str, url: URL):
        for cred in self.__store.credentialsForUrl(url, subject=actor):
            yield cred

    @ipfsOp
    async def onPwStore(self,
                        ipfsop,
                        url: URL,
                        submitUrl: URL,
                        usernameField: str,
                        pwdField: str,
                        username: str,
                        password: str):
        app = runningApp()
        profile = ipfsop.ctx.currentProfile
        ipid = await profile.userInfo.ipIdentifier()

        # Lookup credentials for this URL

        for cred in self.forUrl(ipid.did, url):
            if cred['username_field'] == usernameField and \
               cred['username'] == username:
                # Already have an entry with this username, not overwriting
                return

        dlg = WebCredentialsStoreAskDialog()
        dlg.ui.siteUrl.setText(str(url))
        dlg.ui.siteUrl.setToolTip(str(url))

        dlg.resize(
            app.desktopGeometry.width() * 0.25,
            app.desktopGeometry.height() * 0.15
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
                passwordField=pwdField,
                vaultUser=ipid.did
            )

    def onCreate(self):
        ensure(self.runCreationDialog())

    async def runCreationDialog(self):
        dlg = await runDialogAsync(WebCredentialsCreateDialog)

        if dlg.result() == 1:
            await self.__openVault(dlg.pwd)

    def unlock(self):
        if not runningApp().pwVaultExists():
            ensure(self.runCreationDialog())
        elif not self.__unlocked:
            pwd = inputPassword()

            if not pwd:
                return

            ensure(self.__openVault(pwd))

    @ipfsOp
    async def __openVault(self, ipfsop, pwd: str) -> bool:
        profile = ipfsop.ctx.currentProfile
        ipid = await profile.userInfo.ipIdentifier()

        if not ipid:
            return False

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
        else:
            easyToolTip(
                iPasswordsVaultOpenFailed(),
                self.buttonPos(),
                self,
                4000
            )

        self.updateButton(result)

        return result
