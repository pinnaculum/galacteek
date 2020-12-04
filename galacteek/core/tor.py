import asyncio
import re
import psutil
import platform
import subprocess
import secrets
from os import urandom
from binascii import b2a_hex
from hashlib import sha1

from galacteek import log
from galacteek import ensure
from galacteek import AsyncSignal
from galacteek.core.asynclib import asyncWriteFile


def getTorHashedPassword(secret):
    '''
    https://gist.github.com/jamesacampbell/2f170fc17a328a638322078f42e04cbc
    '''
    # static 'count' value later referenced as "c"
    indicator = chr(96)
    # generate salt and append indicator value so that it
    salt = "%s%s" % (urandom(8), indicator)
    c = ord(salt[8])
    # generate an even number that can be divided in subsequent sections.
    # (Thanks Roman)
    EXPBIAS = 6
    count = (16 + (c & 15)) << ((c >> 4) + EXPBIAS)
    d = sha1()
    # take the salt and append the password
    tmp = salt[:8] + secret
    # hash the salty password
    slen = len(tmp)
    while count:
        if count > slen:
            d.update(tmp.encode())
            count -= slen
        else:
            d.update(tmp[:count].encode())
            count = 0
    hashed = d.digest()

    # Put it all together into the proprietary Tor format.
    salt = b2a_hex(salt[:8].encode()).decode().upper()
    ind = b2a_hex(indicator.encode()).decode()
    h = b2a_hex(hashed).decode().upper()

    return '16:{salt}{i}{h}'.format(
        salt=salt,
        i=ind,
        h=h
    )


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
HashedControlPassword {hashedControlPass}
'''


class TorConfigBuilder:
    def __init__(self, dataDir):
        self._socksPort = None
        self._controlPort = None
        self._dnsPort = None
        self._hostname = '127.0.0.1'
        self._dataDir = dataDir
        self.__controlPass = secrets.token_hex(8)

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
            dataDir=self._dataDir,
            hashedControlPass=getTorHashedPassword(self.__controlPass)
        )


class TorLauncher:
    def __init__(self, configPath, dataDirPath,
                 torPath='tor', debug=True, loop=None):

        self.loop = loop if loop else asyncio.get_event_loop()
        self.exitFuture = asyncio.Future(loop=self.loop)
        self.startedFuture = asyncio.Future(loop=self.loop)

        self._procPid = None
        self._process = None
        self.torPath = torPath
        self.configPath = configPath
        self.dataDirPath = dataDirPath
        self.debug = debug
        self.transport, self.proto = None, None
        self.torCfg = TorConfigBuilder(self.dataDirPath)
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

        # for x in range(0, 12):
        for socksPort in range(9050, 9080):
            # socksPort = unusedTcpPort()

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

                # Wait a bit, if there are port binding issues
                # tor will exit immediately
                await asyncio.sleep(3)

                status = self.process.status()
                assert status in [
                    psutil.STATUS_RUNNING,
                    psutil.STATUS_SLEEPING
                ]
            except Exception as err:
                log.debug(f'Starting TOR failed on port {socksPort} : '
                          f'error {err}')
                self.transport.close()
                continue
            else:
                log.debug(f'Starting TOR OK on port {socksPort}')
                break

    def stop(self):
        self.message('Stopping Tor')
        try:
            if not self.process:
                raise Exception('Process not found')

            self.transport.terminate()
            self._procPid = None
            return True
        except Exception as err:
            self.message(f'Error shutting down daemon: {err}')
            self._procPid = None
            self.terminateException = err
            return False
