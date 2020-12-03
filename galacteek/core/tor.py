import asyncio
import re
import signal
import psutil
import platform
import subprocess
import tempfile

from galacteek import log
from galacteek import ensure
from galacteek import AsyncSignal
from galacteek.core.asynclib import asyncWriteFile
from galacteek.core import unusedTcpPort


class TorProtocol(asyncio.SubprocessProtocol):
    def __init__(self, loop, exitFuture, startedFuture, debug=False):
        self._loop = loop
        self.debug = debug
        self.eventStarted = asyncio.Event()
        self.exitFuture = exitFuture
        self.startedFuture = startedFuture
        self.errAlreadyRunning = False

        self.sTorBootstrapStatus = AsyncSignal(int, str)

    @property
    def loop(self):
        return self._loop

    def pipe_data_received(self, fd, data):
        try:
            msg = data.decode().strip()
        except BaseException:
            return

        for line in msg.split('\n'):
            ma = re.search(
                r'\w*\s\d*\s\d+:\d+:\d+\.\d* \[.*\] '
                r'Bootstrapped (\d+)\%\s\(([\w\_]*)\)',
                line)
            if ma:
                try:
                    pc = ma.group(1)
                    status = ma.group(2)
                    log.debug(f'TOR bootstrapped at {pc} percent: {status}')
                    ensure(self.sTorBootstrapStatus.emit(int(pc), status))
                except Exception:
                    continue

            if self.debug:
                log.debug(f'TOR: {line}')

    def process_exited(self):
        if not self.exitFuture.done():
            self.exitFuture.set_result(True)


torConfigTemplate = '''
SOCKSPort {socksPort}
ControlPort {controlPort}
SOCKSPolicy accept 127.0.0.1
SOCKSPolicy reject *
DNSPort {dnsPort}
AutomapHostsOnResolve 1
AutomapHostsSuffixes .exit,.onion
DataDirectory {dataDir}
'''


class TorConfigBuilder:
    def __init__(self):
        self._socksPort = None
        self._controlPort = None
        self._dnsPort = None
        self._hostname = '127.0.0.1'
        self._dataDir = tempfile.mkdtemp(prefix='gtor')

    @property
    def socksPort(self):
        return self._socksPort

    @property
    def controlPort(self):
        return self._controlPort

    @property
    def dnsPort(self):
        return self._dnsPort

    @property
    def hostname(self):
        return self._hostname

    @socksPort.setter
    def socksPort(self, v):
        self._socksPort = v
        self._controlPort = v + 1
        self._dnsPort = v + 2

    def __str__(self):
        return torConfigTemplate.format(
            socksPort=self.socksPort,
            controlPort=self.controlPort,
            dnsPort=self.dnsPort,
            dataDir=self._dataDir
        )


class TorLauncher:
    def __init__(self, configPath, torPath='tor', debug=True, loop=None):

        self.loop = loop if loop else asyncio.get_event_loop()
        self.exitFuture = asyncio.Future(loop=self.loop)
        self.startedFuture = asyncio.Future(loop=self.loop)

        self._procPid = None
        self._process = None
        self.torPath = torPath
        self.configPath = configPath
        self.debug = debug
        self.transport, self.proto = None, None
        self.torCfg = TorConfigBuilder()
        self.torProto = TorProtocol(self.loop, self.exitFuture,
                                    self.startedFuture,
                                    debug=self.debug)

    @property
    def process(self):
        return self._process

    @process.setter
    def process(self, p):
        if p:
            log.debug(f'Tor process changed, PID: {p.pid}')
        else:
            log.debug('Tor process reset')

        self._process = p

    @property
    def pid(self):
        return self._procPid

    @property
    def running(self):
        return self.pid is not None

    def message(self, msg):
        log.debug(msg)

    async def start(self):
        pCreationFlags = 0

        startupInfo = None
        if platform.system() == 'Windows':
            startupInfo = subprocess.STARTUPINFO()
            startupInfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupInfo.wShowWindow = subprocess.SW_HIDE

        # for socksPort in range(9052, 9080):
        for x in range(0, 12):
            socksPort = unusedTcpPort()

            self.torCfg.socksPort = socksPort
            await asyncWriteFile(self.configPath, str(self.torCfg), 'w+t')

            args = [
                self.torPath,
                '-f', self.configPath
            ]
            log.debug(f'Starting TOR with args: {args}')

            try:
                f = self.loop.subprocess_exec(
                    lambda: self.torProto,
                    *args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    startupinfo=startupInfo,
                    creationflags=pCreationFlags)

                self.transport, self.proto = await f

                self._procPid = self.transport.get_pid()
                self.process = psutil.Process(self._procPid)
            except Exception:
                log.debug(f'Starting TOR failed on port {socksPort}')
                continue
            else:
                log.debug(f'Starting TOR OK on port {socksPort}')
                break

    def stop(self):
        self.message('Stopping Tor')
        try:
            if not self.process:
                raise Exception('Process not found')

            if platform.system() == 'Windows':
                self.process.kill()
            else:
                self.process.send_signal(signal.SIGINT)
                self.process.send_signal(signal.SIGHUP)

            self._procPid = None
            return True
        except Exception as err:
            self.message(f'Error shutting down daemon: {err}')
            self._procPid = None
            self.terminateException = err
            return False
