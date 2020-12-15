import asyncio
import os
from pathlib import Path
from email.message import EmailMessage
# from email.utils import parseaddr as parseEmailAddress
from mailbox import Maildir
# from mailbox import MaildirMessage
import email.errors

from mode import Service
from mode.utils.objects import cached_property

from galacteek import log
from galacteek import AsyncSignal
from galacteek.config import cParentGet
from galacteek.core.process import ProcessLauncher
from galacteek.core.process import LineReaderProcessProtocol
from galacteek.core.process import shellExec
from galacteek.core.asynclib import asyncRmTree

from galacteek.services.bitmessage import bmAddressValid
from galacteek.services.bitmessage.storage import RegularMailDir


class NotBitProtocol(LineReaderProcessProtocol):
    def lineReceived(self, fd, line):
        log.debug(f'Notbit: {line}')

        if line.startswith('Failed to bind socket'):
            log.debug('Notbit failed to start')


class NotBitProcess(ProcessLauncher):
    def __init__(self, dataPath: Path, mailDirPath: Path, listenPort=8444):
        super().__init__()

        self.dataPath = dataPath
        self.objectsPath = self.dataPath.joinpath('objects')
        self.mDirPath = mailDirPath
        self.listenPort = listenPort
        self.useTor = False

    async def startProcess(self):
        if cParentGet('notbit.purgeObjectsOnStartup') is True:
            log.debug(f'Purging objects cache: {self.objectsPath}')

            await asyncRmTree(str(self.objectsPath))

        args = [
            '-m', str(self.mDirPath),
            '-D', str(self.dataPath),
            '-p', str(self.listenPort)
        ]

        if self.useTor:
            args.append('-T')

        await self.runProcess(
            ['notbit'] + args,
            NotBitProtocol(
                self.loop, self.exitFuture, self.startedFuture
            )
        )
        log.debug('Started notbit')


class BitMessageMailManService(Service):
    def __init__(self, mailDirPath: Path, mailBoxesPath: Path):
        super().__init__()
        self.clearMailDirPath = mailDirPath
        self.clearMailDirPath.mkdir(parents=True, exist_ok=True)
        self.clearMailDir = Maildir(str(self.clearMailDirPath))
        self.mailBoxesPath = mailBoxesPath
        self.mailBoxes = {}

        # Signals
        self.sNewMessage = AsyncSignal(str)

    async def loadMailBoxes(self):
        for root, dirs, files in os.walk(str(self.mailBoxesPath)):
            for dir in dirs:
                bma = dir

                if not bmAddressValid(bma):
                    continue

                fp = Path(root).joinpath(bma)
                await self._cMailBox(bma, fp)

                log.debug(f'Loaded mailbox {dir}')

    def mailBoxExists(self, bmAddr):
        return bmAddr in self.mailBoxes

    def mailBoxGet(self, bmAddr):
        return self.mailBoxes.get(bmAddr)

    async def on_start(self) -> None:
        log.debug('Starting BM mailman ..')
        # await self.loadMailBoxes()

    @Service.task
    async def watchMailDir(self):
        while not self.should_stop:
            await asyncio.sleep(2)

            for key in self.clearMailDir.iterkeys():
                try:
                    message = self.clearMailDir[key]
                    recipient = message['To']
                    bmAddr, domain = recipient.split('@')
                    assert domain == 'bitmessage'
                    assert bmAddressValid(bmAddr)
                except email.errors.MessageParseError:
                    continue
                else:
                    # Lookup if we have a mailbox for this recipient
                    mbox = self.mailBoxGet(bmAddr)

                    if not mbox:
                        log.debug(f'No mailbox for {recipient}')
                        await asyncio.sleep(0)
                        continue

                    log.debug(f'Found mailbox for {recipient}')
                    if await mbox.store(message):
                        # Delete the message from notbit's maildir
                        log.debug('Transferred message to maildir')

                        self.clearMailDir.remove(key)
                    else:
                        log.debug('Error Transferring message to maildir')

    async def send(self,
                   bmSource: str,
                   bmDest: str,
                   subject: str,
                   message: str,
                   contentType='text/markdown',
                   encoding='utf-8'):
        """
        Send a BitMessage via notbit-sendmail

        We use text/markdown as the default content-type
        """

        msg = EmailMessage()
        msg['From'] = f'{bmSource}@bitmessage'
        msg['To'] = f'{bmDest}@bitmessage'
        msg['Subject'] = subject
        msg['Content-Type'] = f'{contentType}; charset={encoding.upper()}'

        msg.set_content(message)
        msgBytes = msg.as_bytes()

        pcode, result = await shellExec('notbit-sendmail', input=msgBytes)

        log.debug(f'BM send: {bmSource} {bmDest}: OK')

        return pcode == 0

    async def on_stop(self) -> None:
        log.debug('Stopping BM mailer ..')

    async def createKey(self):
        """
        Create a BitMessage key via notbit-keygen
        """

        code, data = await shellExec('notbit-keygen')
        if data:
            key = data.strip()
            log.debug(f'Bitmessage key generate result: {key}')

            if bmAddressValid(key):
                log.debug(f'Generate bitmessage key {key}')
                return key
            else:
                log.debug(f'Invalid key: {key}')
        else:
            log.debug('Bitmessage key generatation: exec failed')

    async def _cMailBox(self, bmKey, path: Path):
        if bmKey in self.mailBoxes:
            return self.mailBoxGet(bmKey)

        maildir = RegularMailDir(bmKey, path)
        await maildir.setup()

        self.mailBoxes[bmKey] = maildir
        return maildir

    async def createMailBox(self):
        key = await self.createKey()

        if not key:
            # raise Exception('Could not generate BM key')
            return None, None

        fp = self.mailBoxesPath.joinpath(key)
        maildir = await self._cMailBox(key, fp)

        if maildir:
            return key, maildir

    async def getMailBox(self, key):
        fp = self.mailBoxesPath.joinpath(key)
        maildir = await self._cMailBox(key, fp)

        if maildir:
            return key, maildir


class BitMessageClientService(Service):
    notbitProcess: ProcessLauncher = None

    mailer: BitMessageMailManService = None

    @cached_property
    def mailer(self) -> BitMessageMailManService:
        return BitMessageMailManService(
            self.mailDirPath,
            self.mailBoxesPath
        )

    def __init__(self, dataPath: Path):
        super().__init__()

        self.rootPath = dataPath
        self.mailDirPath = self.rootPath.joinpath('maildir')
        self.mailBoxesPath = self.rootPath.joinpath('mailboxes')
        self.notBitDataPath = self.rootPath.joinpath('notbit-data')

    async def on_start(self) -> None:
        if not cParentGet('enabled'):
            log.debug('Bitmessage service is not enabled')
            return

        log.debug('Starting bitmessage client')

        self.rootPath.mkdir(parents=True, exist_ok=True)
        self.mailDirPath.mkdir(parents=True, exist_ok=True)
        self.notBitDataPath.mkdir(parents=True, exist_ok=True)
        self.mailBoxesPath.mkdir(parents=True, exist_ok=True)

        await self.add_runtime_dependency(self.mailer)

        self.notbitProcess = NotBitProcess(
            self.notBitDataPath,
            self.mailDirPath,
            listenPort=cParentGet('notbit.listenPort')
        )
        await self.notbitProcess.start()

    async def on_stop(self) -> None:
        log.debug('Stopping bitmessage client')

        self.notbitProcess.stop()
