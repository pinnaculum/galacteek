import asyncio
import os
from pathlib import Path
from email.message import EmailMessage
# from email.utils import parseaddr as parseEmailAddress
from mailbox import Maildir
# from mailbox import MaildirMessage
import email.errors

from galacteek import log
from galacteek import AsyncSignal
from galacteek import cached_property
from galacteek.config import cParentGet
from galacteek.core.process import ProcessLauncher
from galacteek.core.process import Process
from galacteek.core.process import LineReaderProcessProtocol
from galacteek.core.process import shellExec
from galacteek.core.asynclib import asyncRmTree
from galacteek.core.asynclib import asyncReadFile
from galacteek.core.asynclib import asyncWriteFile
from galacteek.core.aservice import GService

from galacteek.services.bitmessage import bmAddressValid
from galacteek.services.bitmessage.storage import RegularMailDir


NOTBIT = 'notbit'


class NotBitProtocol(LineReaderProcessProtocol):
    def lineReceived(self, fd, line):
        log.debug(f'Notbit: {line}')

        if line.startswith('Failed to bind socket'):
            log.debug('Notbit failed to start')


class NotBitProcess(ProcessLauncher):
    def __init__(self, dataPath: Path, mailDirPath: Path,
                 listenPort=8444,
                 useTor=False):
        super().__init__()

        self.dataPath = dataPath
        self.objectsPath = self.dataPath.joinpath('objects')
        self.pidFilePath = self.dataPath.joinpath('notbit.pid')
        self.logFilePath = self.dataPath.joinpath('notbit.log')
        self.mDirPath = mailDirPath
        self.listenPort = listenPort
        self.useTor = useTor

    def removePidFile(self):
        if self.pidFilePath.is_file():
            log.debug(f'PID file {self.pidFilePath}: unlinking')

            self.pidFilePath.unlink()

    async def startProcess(self):
        if cParentGet('notbit.purgeObjectsOnStartup') is True:
            log.debug(f'Purging objects cache: {self.objectsPath}')

            await asyncRmTree(str(self.objectsPath))

        if self.pidFilePath.is_file():
            # TODO: move to ProcessLauncher

            log.debug(f'PID file {self.pidFilePath} exists, checking process')

            text = await asyncReadFile(str(self.pidFilePath), mode='rt')
            try:
                pid = int(text.split('\n').pop(0))
                prevProc = Process(pid)
                prevProc.terminate()
            except Exception as err:
                log.debug(f'Invalid PID file {self.pidFilePath}: {err}')

            self.removePidFile()

        if self.system == 'Windows':
            args = [
                '-m', str(self.toCygwinPath(self.mDirPath)),
                '-D', str(self.toCygwinPath(self.dataPath))
            ]
        else:
            args = [
                '-m', str(self.mDirPath),
                '-D', str(self.dataPath)
            ]

        args += [
            '-p', str(self.listenPort),
            '-l', str(self.logFilePath)
        ]

        if self.useTor:
            args.append('-T')

        if await self.runProcess(
            [NOTBIT] + args,
            NotBitProtocol(
                self.loop, self.exitFuture, self.startedFuture
            )
        ):
            log.debug(f'Started notbit at PID: {self.process.pid}')

            await asyncWriteFile(
                str(self.pidFilePath),
                f"{self.process.pid}\n",
                mode='w+t'
            )

            return True
        else:
            log.debug('Could not start nobit')

        return False


class BitMessageMailManService(GService):
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

    @GService.task
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
                   mailDir=None,
                   contentType='text/plain',
                   textMarkup='markdown',
                   encoding='utf-8'):
        """
        Send a BitMessage via notbit-sendmail

        We use text/markdown as the default content-type
        """

        msg = EmailMessage()
        msg['From'] = f'{bmSource}@bitmessage'
        msg['To'] = f'{bmDest}@bitmessage'
        msg['Subject'] = subject
        msg['Content-Type'] = \
            f'{contentType}; charset={encoding.upper()}; markup={textMarkup}'

        msg.set_content(message)
        msgBytes = msg.as_bytes()

        pcode, result = await shellExec('notbit-sendmail', input=msgBytes)

        if pcode == 0 and mailDir:
            await mailDir.storeSent(message)

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


class BitMessageClientService(GService):
    notbitProcess: ProcessLauncher = None
    mailer: BitMessageMailManService = None

    ident = 'bitmessage'
    name = 'bitmessage'

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

        if self.which(NOTBIT):
            self.notbitProcess = NotBitProcess(
                self.notBitDataPath,
                self.mailDirPath,
                listenPort=cParentGet('notbit.listenPort'),
                useTor=cParentGet('notbit.useTor')
            )
            if await self.notbitProcess.start():
                await self.psPublish({
                    'type': 'ServiceStarted',
                    'event': {
                        'servicePort': self.notbitProcess.listenPort
                    }
                })
        else:
            log.debug('Notbit could not be found, not starting process')

    async def on_stop(self) -> None:
        log.debug('Stopping bitmessage client')

        if self.notbitProcess:
            self.notbitProcess.stop()
            self.notbitProcess.removePidFile()
