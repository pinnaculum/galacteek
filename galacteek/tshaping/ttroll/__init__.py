import copy
import asyncio
import re
import signal
import psutil

from galacteek import log
from galacteek.config import cSet
from galacteek.config import configForModule
from galacteek.config import configModRegCallback
from galacteek.config import cModuleSave
from galacteek.config.util import OmegaConf
from galacteek.core.tmpf import TmpFile


class TrafficTrollProcessProtocol(asyncio.SubprocessProtocol):
    def __init__(self, loop, exitFuture, startedFuture, debug=False):
        self._loop = loop
        self._debug = debug
        self.eventStarted = asyncio.Event()
        self.exitFuture = exitFuture
        self.startedFuture = startedFuture
        self.errAlreadyRunning = False

    @property
    def loop(self):
        return self._loop

    @property
    def output(self):
        return self._output

    def pipe_data_received(self, fd, data):
        try:
            msg = data.decode().strip()
        except BaseException:
            return

        for line in msg.split('\n'):
            if 'traffictroll' in line and self._debug:
                log.debug(line)

    def process_exited(self):
        if not self.exitFuture.done():
            self.exitFuture.set_result(True)


class TrafficTrollShaper:
    def __init__(self, delay=30, debug=False, loop=None):
        self.loop = loop if loop else asyncio.get_event_loop()
        self.exitFuture = asyncio.Future(loop=self.loop)
        self.startedFuture = asyncio.Future(loop=self.loop)
        self.debug = debug
        self.delay = delay
        self._procPid = None
        # self._process = None

        self._processes = []
        # self.transport, self.proto = None, None

        configModRegCallback(self.onModConfigChange)

    @property
    def process(self):
        return self._process

    @process.setter
    def process(self, p):
        if p:
            log.debug(f'traffictool process changed, PID: {p.pid}')
        else:
            log.debug('traffictool process reset')

        self._process = p

    @property
    def pid(self):
        return self._procPid

    @property
    def running(self):
        return self.pid is not None

    async def onModConfigChange(self):
        pass

    def message(self, msg):
        log.info(msg)

    async def restart(self):
        self.stop()

        await asyncio.sleep(0.2)

        await self.start()

    async def start(self):
        mod = configForModule(__name__)

        if not mod:
            return False

        addrs = psutil.net_if_addrs()
        availIfaces = addrs.keys() if addrs else []

        ifaces = []
        for ifaceregex, _ic in mod.interfaces.items():
            if not _ic.get('enabled') is True:
                continue

            for aiface in availIfaces:
                if re.search(ifaceregex, aiface):
                    ifaces.append(aiface)

        for iface in ifaces:
            cfg = mod.configs.get(iface)

            if not cfg:
                cfg = copy.copy(mod.defaultTtConfig)

                cSet(f'configs.{iface}', cfg)

                cModuleSave()

            cfgF = copy.copy(cfg)
            try:
                cfgF['download'] = str(cfg['download']) + 'kbps'
                cfgF['upload'] = str(cfg['upload']) + 'kbps'

                cfgF['processes']['ipfs']['download'] = \
                    str(cfg['processes']['ipfs']['download']) + 'kbps'
                cfgF['processes']['ipfs']['upload'] = \
                    str(cfg['processes']['ipfs']['upload']) + 'kbps'
            except Exception:
                continue

            proc = await self.startOnInterface(iface, cfgF)

            if not proc:
                continue

    async def startOnInterface(self, iface: str,
                               config: dict):
        try:
            with TmpFile(delete=False) as fp:
                OmegaConf.save(config=config, f=fp.name)

            args = [
                'ttroll',
                iface,
                fp.name,
                '--delay',
                str(self.delay)
            ]

            f = self.loop.subprocess_exec(
                lambda: TrafficTrollProcessProtocol(
                    self.loop, self.exitFuture,
                    self.startedFuture,
                    debug=self.debug),
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            transport, proto = await f

            p = psutil.Process(transport.get_pid())
            self._processes.append(p)

            return p
        except Exception:
            return None

    def stop(self):
        try:
            [p.send_signal(signal.SIGINT) for p in self._processes]
            return True
        except Exception as err:
            self.message(f'Error shutting down: {err}')
            self.terminateException = err
            return False
