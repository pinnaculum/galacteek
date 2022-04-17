import asyncio
import platform
import subprocess
import posixpath
import re

from psutil import Process
from pathlib import Path

from galacteek import log


async def shellExec(arg, input=None, returnStdout=True):
    p = await asyncio.create_subprocess_shell((arg),
                                              stdin=asyncio.subprocess.PIPE,
                                              stdout=asyncio.subprocess.PIPE,
                                              stderr=asyncio.subprocess.PIPE)

    stdout, stderr = await p.communicate(input)
    try:
        if stdout and returnStdout:
            return p.returncode, stdout.decode()
        else:
            return p.returncode, stderr.decode()
    except Exception as err:
        log.debug(f'Exception running {arg}: {err}')
        return None


class BaseProcessProtocol(asyncio.SubprocessProtocol):
    def __init__(self, loop, exitFuture, startedFuture, debug=False):
        self._loop = loop
        self.eventStarted = asyncio.Event()
        self.exitFuture = exitFuture
        self.startedFuture = startedFuture

    @property
    def loop(self):
        return self._loop

    def pipe_data_received(self, fd, data):
        pass

    def process_exited(self):
        if not self.exitFuture.done():
            self.exitFuture.set_result(True)


class LineReaderProcessProtocol(BaseProcessProtocol):
    def lineReceived(self, fd, line):
        pass

    def pipe_data_received(self, fd, data):
        try:
            msg = data.decode().strip()
        except BaseException:
            return

        for line in msg.split('\n'):
            self.lineReceived(fd, line)


class ProcessLauncher:
    _procPid: int = None

    def __init__(self, **kwargs):
        self.loop = asyncio.get_event_loop()
        self.exitFuture = asyncio.Future(loop=self.loop)
        self.startedFuture = asyncio.Future(loop=self.loop)

        self._process = None
        self.transport, self.proto = None, None

    @property
    def system(self):
        return platform.system()

    @property
    def process(self):
        return self._process

    @process.setter
    def process(self, p):
        self._process = p

    @property
    def pid(self):
        return self._procPid

    @property
    def running(self):
        return self.pid is not None

    def message(self, msg):
        log.debug(msg)

    def toCygwinPath(self, path: Path):
        def conv(pp):
            for elem in pp:
                ma = re.search(r'^(c|d|e|f|g|h):', elem.lower())
                if ma:
                    yield '/cygdrive/{d}'.format(d=ma.group(1))
                else:
                    yield elem

        return posixpath.join(*conv(path.parts))

    async def start(self):
        return await self.startProcess()

    async def startProcess(self):
        return False

    async def runProcess(self, args, proto, nice=None):
        try:
            startupInfo = None
            if platform.system() == 'Windows':
                startupInfo = subprocess.STARTUPINFO()
                startupInfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupInfo.wShowWindow = subprocess.SW_HIDE

            f = self.loop.subprocess_exec(
                lambda: proto,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                startupinfo=startupInfo
            )

            self.transport, self.proto = await f

            self._procPid = self.transport.get_pid()
            self.process = Process(self._procPid)

            if isinstance(nice, int) and nice in range(-20, 20):
                self.process.nice(nice)
        except Exception as err:
            log.debug(f'Could not run process with args {args}: {err}')
            if self.transport:
                self.transport.close()

            return False
        else:
            return True

    def stop(self):
        try:
            if not self.process:
                raise Exception('Process not found')

            self.transport.terminate()
            self._procPid = None
            return True
        except Exception as err:
            self.message(f'Error shutting down process: {err}')
            self._procPid = None
            return False
