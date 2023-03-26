import traceback
from pathlib import Path
from yarl import URL

from vicious_vault.vault import ViciousVault
from vicious_vault import NoVaultPasswordError
from vicious_vault import AccessDeniedError

from galacteek.core import utcDatetimeIso


def rawUrl(fullUrl: URL):
    return fullUrl.with_path('/').with_query('').with_fragment('')


class PasswordsVault(ViciousVault):
    @property
    def passwords(self):
        return self.data['passwords']


class CredentialsStore:
    def __init__(self, vaultPath: Path):
        self.__pwVault = PasswordsVault(path=vaultPath)

    def open(self, pwd: str,
             user: str = 'nobody') -> bool:
        """
        Open/create the vault with the given password
        """
        try:
            assert len(pwd) > 0

            self.__pwVault.load(pwd, user=user)
        except AccessDeniedError:
            traceback.print_exc()
            return False
        except (NoVaultPasswordError, AssertionError):
            traceback.print_exc()
            return False
        except Exception:
            traceback.print_exc()
            return False
        else:
            return True

    def close(self) -> bool:
        return self.__pwVault.close()

    def aclAllow(self, s: str, obj: str, act: str) -> bool:
        return self.__pwVault.policy_add(s, obj, act)

    def credentialsForUrl(self, url: URL,
                          subject: str = None):
        """
        Yields the credentials found for a given URL
        """
        try:
            urls = str(url)
            user = subject if subject else self.__pwVault.subject_default

            with self.__pwVault.reader(user) as rctx:
                passwords = rctx.data['passwords']

                for domainUrl, dcfg in passwords.items():
                    entries = dcfg.get(urls, [])

                    for pwd in entries:
                        yield pwd
        except AccessDeniedError:
            raise
        except Exception:
            traceback.print_exc()

    def _storeCredentials(self,
                          fullUrl: URL,
                          formSubmitUrl: URL,
                          username: str,
                          password: str,
                          usernameField: str = 'username',
                          passwordField: str = 'password',
                          vaultUser: str = 'nobody'):
        try:
            domainUrl = str(rawUrl(fullUrl))

            full = str(fullUrl.with_query('').with_fragment(''))

            with self.__pwVault.writer(vaultUser) as wctx:
                passwords = wctx.data['passwords']
                cfg = passwords.get(domainUrl)

                # if domainUrl not in self.__pwVault.passwords:
                if domainUrl not in passwords:
                    cfg = {}

                    passwords[domainUrl] = cfg

                e = cfg.setdefault(full, [])
                now = utcDatetimeIso()

                e.append({
                    'username_field': usernameField,
                    'password_field': passwordField,
                    'form_submit_url': str(formSubmitUrl),
                    'username': username,
                    'password': password,
                    'date_created': now,
                    'date_modified': now,
                    'date_accessed_last': now
                })

                self.__pwVault.save()
        except Exception:
            traceback.print_exc()

    sc = _storeCredentials

    def onPwVaultStoreReq(self,
                          baseUrl: URL,
                          formSubmitUrl: URL,
                          usernameField: str,
                          passwordField: str,
                          username: str,
                          password: str):
        self.sc(baseUrl,
                formSubmitUrl,
                username,
                password,
                usernameField=usernameField,
                passwordField=passwordField)
