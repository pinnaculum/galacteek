import asyncio
import traceback
import base64
from io import BytesIO
from pathlib import Path
from email.message import EmailMessage
from email.parser import BytesParser

from mailbox import Maildir
from mailbox import MaildirMessage

from galacteek import log
from galacteek import AsyncSignal
from galacteek import database

from galacteek.config import cParentGet


class BitMessageMailDir:
    bmAddress: str = None

    folderInbox: Maildir = None
    folderSent: Maildir = None
    folderTrash: Maildir = None

    def __init__(self, bmAddr: str, mailDirPath: Path):
        self.bmAddress = bmAddr
        self.path = mailDirPath
        self.maildir = Maildir(str(self.path))

        self.sNewMessage = AsyncSignal(str, EmailMessage)

    async def setup(self):
        self.path.mkdir(parents=True, exist_ok=True)
        self.folderInbox = self.maildir.add_folder('Inbox')
        self.folderSent = self.maildir.add_folder('Sent')
        self.folderTrash = self.maildir.add_folder('Trash')

    async def emitNewMessage(self, key, msg):
        await self.sNewMessage.emit(key, msg)

    async def storeWelcome(self):
        contact = await database.bmContactByNameFirst(
            'galacteek-support'
        )

        if not contact:
            # not found
            return

        body = cParentGet('messages.welcome.body')

        msg = EmailMessage()
        msg['From'] = f'{contact.bmAddress}@bitmessage'
        msg['To'] = f'{self.bmAddress}@bitmessage'
        msg['Subject'] = 'BitMessage is easy'

        msg.set_payload(body)

        await self.store(msg)

    async def yieldNewMessages(self):
        for key in self.folderInbox.iterkeys():
            msg = await self.getMessageByKey(key)
            if msg:
                yield key, msg

    async def store(self, message):
        raise Exception('Not implemented')

    async def storeSent(self, message):
        raise Exception('Not implemented')

    def msgRemoveInbox(self, messageId):
        try:
            self.folderInbox.remove(messageId)
            self.maildir.flush()
            return True
        except Exception as err:
            log.debug(f'Could not remove inbox message {messageId}: {err}')
            return False

    def updateMessage(self, mKey, msg):
        try:
            self.folderInbox[mKey] = msg
            return True
        except Exception as err:
            log.debug(f'updateMessage failed: {err}')
            return False


class EncryptedMailDir(BitMessageMailDir):
    def __init__(self, bmAddr: str, mailDirPath: Path):
        super().__init__(bmAddr, mailDirPath)
        self.parser = BytesParser()

    async def getMessageByKey(self, key):
        try:
            message = self.folderInbox[key]
            payload = base64.b64decode(
                message.get_payload().encode())

            decoded = await self.rsaExec.decryptData(
                BytesIO(payload),
                self.privKey)
            msg = self.parser.parsebytes(decoded)
        except Exception:
            traceback.print_exc()
        else:
            await asyncio.sleep(0.1)
            log.debug(f'Decoded message (key: {key})')
            return msg

    async def setup(self):
        from galacteek.crypto.rsa import RSAExecutor
        self.rsaExec = RSAExecutor()

        # TODO: attach external keys (this is temporary)
        self.privKey, self.pubKey = await self.rsaExec.genKeys()

        self.path.mkdir(parents=True, exist_ok=True)
        self.folderInbox = self.maildir.add_folder('new')

    async def encryptMessage(self, message):
        from io import BytesIO
        try:
            body = bytes(message)

            encrypted = await self.rsaExec.encryptData(
                BytesIO(body), self.pubKey)
            payload = base64.b64encode(encrypted).decode()
        except Exception as e:
            raise e
        else:
            eMessage = MaildirMessage()
            eMessage['From'] = 'RIP-SMTP@localhost.nsa'
            eMessage.set_payload(payload)
            return eMessage

    async def store(self, message):
        log.debug('Storing message in encrypted maildir ..')
        try:
            eMsg = await self.encryptMessage(message)
            if eMsg:
                self.folderInbox.add(eMsg)
            else:
                raise Exception('Could not encrypt message')
        except Exception as err:
            traceback.print_exc()
            print('ERR')
            print(str(err))
            return False
        else:
            return True


class RegularMailDir(BitMessageMailDir):
    folderInbox: Maildir = None

    async def store(self, message):
        log.debug('Storing message in maildir ..')
        try:
            key = self.folderInbox.add(message)
        except Exception as err:
            log.debug(str(err))
            traceback.print_exc()
        else:
            await self.emitNewMessage(key, message)
            return True

    async def storeSent(self, message):
        log.debug('Storing message in outbox ..')
        try:
            key = self.folderSent.add(message)
            log.debug(f'Sent mail key: {key}')
        except Exception as err:
            log.debug(str(err))

    async def getMessageByKey(self, key):
        try:
            message = self.folderInbox[key]
        except Exception as err:
            log.debug(str(err))
            traceback.print_exc()
        else:
            await asyncio.sleep(0.1)
            return message
