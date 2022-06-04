import os
import os.path
import asyncio
import re
import json
import signal
import aioipfs
import aiofiles
import orjson
import psutil
import platform
import subprocess
import traceback
from pathlib import Path

from galacteek import log
from galacteek.config import cGet
from galacteek.config.util import ocToContainer
from galacteek.config.cmods import ipfs as cmodipfs
from galacteek.core import utcDatetimeIso
from galacteek.core.tmpf import TmpFile
from galacteek.core.jsono import DotJSON
from galacteek.core.asynclib import asyncWriteFile
from galacteek.core.asynclib import asyncReadFile
from galacteek.core.ps import hubPublish
from galacteek.core.ps import key42


def boolarg(arg):
    return str(arg).lower()


async def shell(arg):
    p = await asyncio.create_subprocess_shell((arg),
                                              stdin=asyncio.subprocess.PIPE,
                                              stdout=asyncio.subprocess.PIPE)

    stdout, stderr = await p.communicate()
    try:
        if p.returncode != 0:
            out = stdout.decode() if stdout else None
            err = stderr.decode() if stderr else None
            return False, out, err

        try:
            return True, stdout.decode(), None
        except Exception:
            return True, None, None
    except Exception as err:
        log.debug(f'Exception running {arg}: {err}')
        return False, None, None


async def ipfsConfig(binPath, param, value):
    ok, out, err = await shell("{0} config '{1}' '{2}'".format(
        binPath, param, value))
    if err:
        log.warning(f'ipfsConfig({param}) with value {value}, error: {err}')
        return False
    else:
        log.debug(f'ipfsConfig({param}) with value {value}, OK')
        return True


async def ipfsConfigShow(binPath):
    ok, out, err = await shell(f"{binPath} config show")
    if err:
        return False, None
    else:
        try:
            cfg = json.loads(out)
        except Exception as err:
            log.debug(f'ipfsConfigShow error: {err}')
            return False, None
        else:
            log.debug('ipfsConfigShow: OK')
            return True, cfg


async def ipfsConfigReplace(binPath, newCfgPath):
    log.debug(f'ipfsConfigReplace: {newCfgPath}')

    ok, out, err = await shell(f"{binPath} config replace {newCfgPath}")
    if err:
        return False
    else:
        return True


async def ipfsConfigProfileApply(binPath, profile):
    return await shell("{0} config profile apply {1}".format(
        binPath, profile))


async def ipfsConfigJson(binPath, param, value):
    ok, out, err = await shell("{0} config --json '{1}' '{2}'".format(
        binPath, param, json.dumps(value)))
    if err:
        log.warning(
            f'ipfsConfigJson({param}) with value {value}, error: {err}')
        return False
    else:
        log.debug(f'ipfsConfigJson({param}) with value {value}, OK')
        return True


async def ipfsConfigGetJson(binPath, param):
    ok, out, err = await shell(
        "{0} config --json '{1}'".format(binPath, param))
    if ok is True:
        try:
            return orjson.loads(out)
        except Exception:
            return None

    return None


async def ipfsMigrateRepo():
    return await shell("fs-repo-migrations -y")


class IPFSDProtocol(asyncio.SubprocessProtocol):
    """
    IPFS daemon process protocol

    This handles output from the IPFS daemon
    """

    def __init__(self, loop, exitFuture, startedFuture, debug=False):
        self._loop = loop
        self._debug = debug
        self._output = bytearray()
        self.eventStarted = asyncio.Event()
        self.exitFuture = exitFuture
        self.startedFuture = startedFuture
        self.apiStarted = False
        self.gatewayStarted = False
        self.swarmStarted = False
        self.daemonReady = False
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

        # The output we expect might be different in earlier versions
        # i've mainly tested with go-ipfs > 0.4.11
        # TODO: implement ipfs process supervisor independent of daemon output

        for line in msg.split('\n'):
            if self._debug:
                # go-ipfs output
                log.debug(line)
            if re.search('Error: ipfs daemon is running', line):
                self.errAlreadyRunning = True
            if re.search('Gateway.*server listening on', line):
                self.gatewayStarted = True
            if re.search('Swarm listening on', line):
                self.swarmStarted = True
            if re.search('API server listening', line):
                self.apiStarted = True
            if re.search('Daemon is ready', line):
                self.daemonReady = True
            if re.search('Error:', line):
                pass

        if self.daemonReady is True:
            if not self.startedFuture.done():
                self.startedFuture.set_result(True)
            self.eventStarted.set()

        self._output.extend(data)

    def process_exited(self):
        if not self.exitFuture.done():
            self.exitFuture.set_result(True)


class GoIPFSConfigurator(DotJSON):
    pass


DEFAULT_APIPORT = 5001
DEFAULT_SWARMPORT = 4001
DEFAULT_WS_SWARMPORT = 4011
DEFAULT_GWPORT = 8080


class AsyncIPFSDaemon(object):
    """
    Async IPFS daemon subprocess wrapper

    :param str repopath: IPFS repository path
    :param int apiport: API port number to listen on
    :param int swarmport: Swarm port number to listen on
    :param int gatewayport: HTTP GW port number to listen on
    :param int swarmLowWater: min swarm connections
    :param int swarmHighWater: max swarm connections
    :param int storageMax: max repository storage capacity, in GB
    :param bool pubsubEnable: enable pubsub
    :param bool noBootstrap: empty bootstrap
    :param bool corsEnable: enable CORS
    :param bool p2pStreams: enable P2P streams support
    :param bool gwWritable: make the HTTP gateway writable
    """

    def __init__(self, repopath: Path,
                 goIpfsPath='ipfs',
                 statusPath=None,
                 apiport=DEFAULT_APIPORT,
                 swarmport=DEFAULT_SWARMPORT,
                 swarmportWs=DEFAULT_WS_SWARMPORT,
                 swarmportQuic=DEFAULT_SWARMPORT,
                 swarmProtos=['tcp', 'quic'],
                 gatewayport=DEFAULT_GWPORT, initRepo=True,
                 swarmLowWater=10, swarmHighWater=20, nice=19,
                 pubsubEnable=False, noBootstrap=False, corsEnable=True,
                 pubsubRouter='floodsub', namesysPubsub=False,
                 pubsubSigning=False, offline=False,
                 acceleratedDht=False,
                 fileStore=False,
                 profiles=[],
                 dataStore=None,
                 detached=True, autoRestart=True,
                 p2pStreams=True, migrateRepo=False, routingMode='dht',
                 gwWritable=False, storageMax=20,
                 ipfsNetwork='main',
                 debug=False, loop=None):

        self.loop = loop if loop else asyncio.get_event_loop()
        self.exitFuture = asyncio.Future(loop=self.loop)
        self.startedFuture = asyncio.Future(loop=self.loop)
        self.repoPath = repopath
        self.repoApiFilePath = self.repoPath.joinpath('api')
        self.repoConfigPath = self.repoPath.joinpath('config')
        self.repoKeyStorePath = self.repoPath.joinpath('keystore')
        self.repoVersionPath = self.repoPath.joinpath('version')
        self.statusPath = statusPath
        self.detached = detached
        self.acceleratedDht = acceleratedDht
        self.autoRestart = autoRestart
        self.goIpfsPath = goIpfsPath
        self.apiport = apiport
        self.gatewayport = gatewayport
        self.swarmport = swarmport
        self.swarmportWs = swarmportWs
        self.swarmportQuic = swarmportQuic
        self.swarmProtos = swarmProtos
        self.swarmLowWater = swarmLowWater
        self.swarmHighWater = swarmHighWater
        self.storageMax = storageMax
        self.initRepo = initRepo
        self.fileStore = fileStore
        self.namesysPubsub = namesysPubsub
        self.pubsubEnable = pubsubEnable
        self.pubsubRouter = pubsubRouter
        self.pubsubSigning = pubsubSigning
        self.corsEnable = corsEnable
        self.p2pStreams = p2pStreams
        self.noBootstrap = noBootstrap
        self.migrateRepo = migrateRepo
        self.gwWritable = gwWritable
        self.routingMode = routingMode

        self.ipfsNetworkName = ipfsNetwork if ipfsNetwork else 'main'

        self.ipfsNetworkRunningUri = None

        self.profiles = profiles
        self.dataStore = dataStore
        self.offline = offline
        self.nice = nice
        self.debug = debug

        self._procPid = None
        self._process = None
        self._msgCallback = []

        self.daemonClient = self.client()
        self.transport, self.proto = None, None

        self._createRepoDir()

    @property
    def process(self):
        return self._process

    @process.setter
    def process(self, p):
        if p:
            log.debug(f'go-ipfs process changed, PID: {p.pid}')
        else:
            log.debug('go-ipfs process reset')

        self._process = p

    @property
    def pid(self):
        return self._procPid

    @property
    def running(self):
        return self.pid is not None

    @property
    def swarmKeyPath(self):
        # Returns the path to the 'swarm.key' file for this daemon's repo

        if self.repoPath and self.repoPath.is_dir():
            return self.repoPath.joinpath('swarm.key')

    def addMessageCallback(self, cb):
        self._msgCallback.append(cb)

    def rmMessageCallback(self, cb):
        try:
            self._msgCallback.remove(cb)
        except Exception:
            pass

    def _createRepoDir(self):
        if not self.repoPath.is_dir():
            self.repoPath.mkdir(parents=True, exist_ok=True)

    def repoExists(self):
        if not self.repoConfigPath.is_file() or \
                not self.repoKeyStorePath.is_dir():
            log.debug(f'Repository located at {self.repoPath} does not exist')
            return False

        return True

    def repoVersion(self):
        if self.repoVersionPath.is_file():
            try:
                with open(str(self.repoVersionPath), 'rt') as fdv:
                    version = fdv.readline()
                    return int(version)
            except Exception:
                log.debug(
                    f'Could not read version from {self.repoVersionPath}')

    def availableProfiles(self):
        return [
            'lowpower',
            'randomports',
            'local-discovery',
            'test',
            'server',
            'default-networking'
        ]

    def message(self, msg):
        log.debug(msg)

        for cb in self._msgCallback:
            cb(msg)

    def publishEvent(self, event):
        hubPublish(key42, {
            'event': event
        })

    def publishReconnectingEvent(self):
        self.publishEvent({
            'type': 'IpfsDaemonResumeEvent',
            'ipfsNetworkName': self.ipfsNetworkName,
            'ipfsNetworkUri': self.ipfsNetworkRunningUri
        })

    async def switchNetworkByName(self, networkName: str):
        self.autoRestart = False
        self.stop()

        await self.restart(ipfsNetworkName=networkName)

        self.autoRestart = True

    async def restart(self, ipfsNetworkName=None):
        self.message('Restarting daemon')

        async for pct, msg in self.start(ipfsNetworkName=ipfsNetworkName):
            self.message(msg)

    async def start(self, ipfsNetworkName=None):
        # Set the IPFS_PATH environment variable
        os.environ['IPFS_PATH'] = str(self.repoPath)

        switchingNetwork = ipfsNetworkName is not None  # noqa

        if ipfsNetworkName:
            self.ipfsNetworkName = ipfsNetworkName
            self.ipfsNetworkRunningUri = None

        ipfsNetCfg = cmodipfs.ipfsNetworkConfig(self.ipfsNetworkName)

        if ipfsNetCfg is None:
            # Load the 'main' network if that network can't be found
            self.ipfsNetworkName = 'main'
            ipfsNetCfg = cmodipfs.ipfsNetworkConfig(self.ipfsNetworkName)

        self.message('Using go-ipfs binary: {}'.format(self.goIpfsPath))

        if not self.repoExists():
            self.message('Initializing IPFS repository: {repo}'.format(
                repo=self.repoPath))
            yield 10, f'Initializing IPFS repository: {self.repoPath}'

            if isinstance(self.dataStore, str):
                yield 20, f'Creating repos with datastore: {self.dataStore}'
                await shell(f'ipfs init -p {self.dataStore}')
            else:
                yield 20, 'Creating repos with default datastore'
                await shell('ipfs init')

            yield 20, 'Repository initialized'

        repoV = self.repoVersion()

        if isinstance(repoV, int) and repoV < 11:
            # Migrate
            self.message('Detected repository version {repoV}, migrating')

            yield 25, 'Running migration'
            await ipfsMigrateRepo()
            yield 30, 'Migration finished'
        else:
            yield 25, 'No migration needed'

        if self.repoApiFilePath.exists():
            self.repoApiFilePath.unlink()

        yield 30, 'Configuring swarm key ...'

        swarmKey = cmodipfs.ipfsNetworkSwarmKey(self.ipfsNetworkName)
        privNetwork = False

        if isinstance(swarmKey, str):
            # We have a swarm key
            try:
                await asyncWriteFile(str(self.swarmKeyPath),
                                     swarmKey,
                                     mode='w+t')

                # Enforce
                os.environ['LIBP2P_FORCE_PNET'] = '1'

                privNetwork = True
            except Exception as err:
                log.warning(f'Error writing swarm key '
                            f'to file: {self.swarmKeyPath}: {err}')
        else:
            # We're not using a swarm key, remove it if it exists
            if 'LIBP2P_FORCE_PNET' in os.environ:
                os.environ.pop('LIBP2P_FORCE_PNET')

            if self.swarmKeyPath.is_file():
                self.swarmKeyPath.unlink()

        yield 35, 'Reading current configuration ..'

        ok, startConfig = await ipfsConfigShow(self.goIpfsPath)
        if not ok:
            raise Exception("Could not read go-ipfs's configuration")

        goIpfsC = GoIPFSConfigurator(startConfig)

        bstrapInit, bstrapInitPath = None, self.repoPath.joinpath(
            f'bootstrap.init.{self.ipfsNetworkName}'
        )

        if self.ipfsNetworkName == 'main':
            if not bstrapInitPath.is_file() and goIpfsC.Bootstrap:
                # Save a copy of the initial boostrap
                # The bootstrap is pretty much the only config item we want
                # to keep a record of

                await asyncWriteFile(
                    str(bstrapInitPath),
                    orjson.dumps(goIpfsC.Bootstrap),
                    'wb'
                )

        try:
            loaded = orjson.loads(
                await asyncReadFile(str(bstrapInitPath))
            )
            assert isinstance(loaded, list) and len(loaded) > 0
        except Exception:
            bstrapInit = None
        else:
            bstrapInit = loaded

        with TmpFile(mode='w+t', delete=False) as newCfgFile:
            goIpfsC.Addresses.API = \
                f'/ip4/127.0.0.1/tcp/{self.apiport}'
            goIpfsC.Addresses.Gateway = \
                f'/ip4/127.0.0.1/tcp/{self.gatewayport}'

            yield 40, 'Configuring multiaddrs ..'

            # Swarm multiaddrs (ipv4 and ipv6), TCP and quic
            swarmAddrs = []

            if 'quic' in self.swarmProtos:
                swarmAddrs += [
                    '/ip4/0.0.0.0/udp/{swarmport}/quic'.format(
                        swarmport=self.swarmportQuic),
                    '/ip6/::/udp/{swarmport}/quic'.format(
                        swarmport=self.swarmportQuic)
                ]

            if 'tcp' in self.swarmProtos or not swarmAddrs:
                swarmAddrs += [
                    '/ip4/0.0.0.0/tcp/{swarmport}'.format(
                        swarmport=self.swarmport),
                    '/ip4/0.0.0.0/tcp/{swarmportWs}/ws'.format(
                        swarmportWs=self.swarmportWs),
                    '/ip6/::/tcp/{swarmport}'.format(
                        swarmport=self.swarmport)
                ]

            goIpfsC.Addresses.Swarm = swarmAddrs

            yield 50, 'Configuring connection manager ..'

            # Swarm connection manager parameters
            goIpfsC.Swarm.ConnMgr.LowWater = self.swarmLowWater
            goIpfsC.Swarm.ConnMgr.HighWater = self.swarmHighWater
            goIpfsC.Swarm.ConnMgr.GracePeriod = '60s'

            yield 55, 'Configuring boostrap ..'

            if privNetwork is True:
                # Private network: set the bootstrap list

                goIpfsC.Bootstrap = list(ipfsNetCfg.get('bootstrap', []))
            else:
                if self.ipfsNetworkName == 'main' and bstrapInit:
                    # Reuse the initial bootstrap
                    goIpfsC.Bootstrap = bstrapInit

            yield 60, 'Configuring pubsub/p2p ..'

            goIpfsC.Routing.Type = self.routingMode

            if self.pubsubRouter in ['floodsub', 'gossipsub']:
                goIpfsC.Pubsub.Router = self.pubsubRouter

            # goIpfsC.Pubsub.DisableSigning = not self.pubsubSigning
            goIpfsC.Swarm.DisableBandwidthMetrics = False

            # Maximum storage
            goIpfsC.Datastore.StorageMax = f'{self.storageMax}GB'

            # P2P streams
            goIpfsC.Experimental.Libp2pStreamMounting = self.p2pStreams

            # Filestore
            goIpfsC.Experimental.FilestoreEnabled = self.fileStore

            # Accelerated DHT client
            goIpfsC.Experimental.AcceleratedDHTClient = self.acceleratedDht

            # CORS
            if self.corsEnable:
                httpHeaders = goIpfsC.API.HTTPHeaders
                httpHeaders.Access__Control__Allow__Credentials = \
                    ['true']
                httpHeaders.Access__Control__Allow__Methods = \
                    ["GET", "POST"]
                httpHeaders.Access__Control__Allow__Origin = \
                    ["*"]

            if self.noBootstrap:
                goIpfsC.Bootstrap = []

            goIpfsC.Gateway.Writable = self.gwWritable

            goIpfsC.write(newCfgFile)
            newCfgFile.flush()

            await asyncio.sleep(0)

            result = await ipfsConfigReplace(self.goIpfsPath, newCfgFile.name)
            if not result:
                raise Exception('Could not replace config')

        await asyncio.sleep(0)
        await self.profilesListApply(self.profiles)

        args = [self.goIpfsPath, 'daemon']

        if self.pubsubEnable:
            args.append('--enable-pubsub-experiment')

        if self.namesysPubsub:
            args.append('--enable-namesys-pubsub')

        if self.migrateRepo:
            args.append('--migrate')

        if self.offline:
            args.append('--offline')

        pCreationFlags = 0

        yield 80, 'Starting subprocess ..'

        startupInfo = None
        if platform.system() == 'Windows':
            startupInfo = subprocess.STARTUPINFO()
            startupInfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupInfo.wShowWindow = subprocess.SW_HIDE

        if self.detached:
            f = self.loop.subprocess_exec(
                lambda: IPFSDProtocol(self.loop, self.exitFuture,
                                      self.startedFuture,
                                      debug=self.debug),
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
                close_fds=False,
                startupinfo=startupInfo,
                creationflags=pCreationFlags)
        else:
            f = self.loop.subprocess_exec(
                lambda: IPFSDProtocol(self.loop, self.exitFuture,
                                      self.startedFuture,
                                      debug=self.debug),
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                startupinfo=startupInfo,
                creationflags=pCreationFlags)

        self.transport, self.proto = await f

        self._procPid = self.transport.get_pid()
        self.process = psutil.Process(self._procPid)
        self.setProcNiceness(nice=self.nice, proc=self.process)

        # Set the running IPFS network URI
        self.ipfsNetworkRunningUri = ipfsNetCfg.get('uri')

        # Publish a pubsub event message
        self.publishEvent({
            'type': 'IpfsDaemonStartedEvent',
            'ipfsNetworkName': self.ipfsNetworkName,
            'ipfsNetworkUri': self.ipfsNetworkRunningUri
        })

        yield 100, 'go-ipfs started'

    async def profilesListApply(self, profiles):
        for profile in profiles:
            if profile and profile in self.availableProfiles():
                await self.profileApply(profile)

    async def profileApply(self, profile):
        self.message(f'Applying daemon profile {profile}')
        await ipfsConfigProfileApply(self.goIpfsPath, profile)

    async def watchProcess(self):
        while True:
            await asyncio.sleep(30)

            try:
                status = self.process.status()
                self.message(f'go-ipfs (PID: {self.process.pid}): '
                             f'status: {status}')
            except psutil.NoSuchProcess as err:
                self.message(f'go-ipfs (PID: {self.process.pid}): '
                             f'NoSuchProcess error: {err}')

                self.publishEvent({
                    'type': 'IpfsDaemonGoneEvent'
                })

                if self.autoRestart is True:
                    self.message(f'go-ipfs (PID: {self.process.pid}): '
                                 'Restarting!')
                    self._procPid = None
                    self.process = None
                    await self.restart()
                    await asyncio.sleep(10)
            except Exception as err:
                if not self.process:
                    # Understandable ..
                    # We could be in the process of restarting
                    continue
                else:
                    self.message(f'go-ipfs (PID: {self.process.pid}): '
                                 f'Unknown error: {err}')
                    continue
            else:
                if status in [
                        psutil.STATUS_STOPPED,
                        psutil.STATUS_ZOMBIE,
                        psutil.STATUS_DEAD]:
                    self.message(f'go-ipfs (PID: {self.process.pid}): '
                                 f'seems to be stopped ?')
                    if self.autoRestart is True:
                        self._procPid = None
                        self.process = None
                        await self.restart()
                        await asyncio.sleep(10)

            await self.writeStatus()

    async def writeStatus(self):
        client = self.daemonClient

        try:
            ident = await client.core.id()

            if self.process and ident:
                # Remember orjson.dumps returns bytes

                async with aiofiles.open(str(self.statusPath), 'w+b') as fd:
                    await fd.write(orjson.dumps({
                        'ident': ident,
                        'pid': self.process.pid,
                        'status': self.process.status(),
                        'date': utcDatetimeIso()
                    }))

                return True
            else:
                raise Exception(
                    "Could not get ident, what's going on ?")
        except aioipfs.APIError:
            return False
        except Exception as e:
            self.message(f'Status write error: {e}, postponing')
            return False

    def client(self):
        return aioipfs.AsyncIPFS(host='127.0.0.1',
                                 port=self.apiport, loop=self.loop)

    async def loadStatus(self):
        client = self.daemonClient
        try:
            async with aiofiles.open(str(self.statusPath), 'r') as fd:
                status = orjson.loads(await fd.read())
                assert 'ident' in status
                assert 'pid' in status

            proc = psutil.Process(status['pid'])

            if proc.status() in [
                    psutil.STATUS_RUNNING,
                    psutil.STATUS_SLEEPING]:
                ident = await client.core.id()
                assert ident['ID'] == status['ident']['ID']

                self._procPid = proc.pid
                self.process = proc
                return True, client
            else:
                return False, None
        except aioipfs.APIError as e:
            self.message(f'Error loading status: {e.message}')
            return False, None
        except psutil.NoSuchProcess:
            self.message('Process is gone')
            return False, None
        except Exception as e:
            self.message(f'Error loading status: {e}')
            return False, None

    async def ipfsConfig(self, param, value):
        return await ipfsConfig(self.goIpfsPath, param, value)

    async def ipfsConfigJson(self, param, value):
        return await ipfsConfigJson(self.goIpfsPath, param, value)

    async def ipfsConfigGetJson(self, param):
        return await ipfsConfigGetJson(self.goIpfsPath, param)

    async def ipfsConfigPeeringGet(self):
        pl = await self.ipfsConfigGetJson('Peering.Peers')
        return pl if pl else []

    async def ipfsConfigPeeringAdd(self, peerId, addrs=[]):
        """
        Add a peer in the Peering.Peers config parameter
        (new peering system in go-ipfs 0.6)
        """

        pList = await self.ipfsConfigPeeringGet()

        entry = {
            'ID': peerId,
            'Addrs': addrs
        }

        try:
            if not any(e['ID'] == peerId for e in pList):
                pList.append(entry)
        except Exception:
            pList = [entry]

        await self.ipfsConfigPeeringSet(pList)

    async def ipfsConfigPeeringSet(self, pList: list):
        try:
            return await self.ipfsConfigJson(
                'Peering.Peers',
                pList
            )
        except Exception as err:
            log.debug(f'Peering config set error: {err}')
            traceback.print_exc()
        else:
            log.debug(f'Peering config set: {len(pList)} entries')

    async def peeringConfigure(self):
        try:
            cProvidersDb = cGet('peering.contentProvidersDb',
                                mod='galacteek.ipfs')
            default = cProvidersDb.get('defaultSet')

            provUse = cProvidersDb.get('use')
            cProviders = ocToContainer(cProvidersDb[default])
        except Exception as err:
            traceback.print_exc()
            log.debug(f'peeringConfigure: could not load DB: {err}')
            return False

        pInit = await self.ipfsConfigPeeringGet()

        if not pInit:
            pInit = []

        for provName, conns in cProviders.items():
            use = provUse.get(provName, False)

            if use is not True:
                # Don't use this provider
                log.debug(f'peeringConfigure: not using provider: {provName}')
                continue

            for conn in conns:
                if not isinstance(conn, dict):
                    log.debug(f'peeringConfigure: Invalid entry: {conn}')
                    continue

                if 'ID' not in conn or 'Addrs' not in conn:
                    log.debug(f'peeringConfigure: Invalid entry: {conn}')
                    continue

                if not any(e['ID'] == conn['ID'] for e in pInit):
                    pInit.append(conn)

                    await asyncio.sleep(0)

        await self.ipfsConfigPeeringSet(pInit)

        return True

    def getProcNiceness(self, proc=None):
        process = proc if proc else self.process

        try:
            nice = process.nice()
            self.message(f'Process {process.pid}: current nice is {nice}')
            return nice
        except Exception:
            return None

    def setProcNiceness(self, nice=19, proc=None):
        process = proc if proc else self.process

        try:
            if not isinstance(process, psutil.Process):
                raise ValueError('Invalid process')

            self.message(f'Applying limits to process: {process.pid}')

            if platform.system() == 'Windows':
                if nice in range(10, 21):
                    self.message('Process Priority class: below normal')
                    process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                elif nice in range(0, 10):
                    self.message('Process Priority class: normal')
                    process.nice(psutil.NORMAL_PRIORITY_CLASS)
                elif nice in range(-10, 0):
                    self.message('Process Priority class: above normal')
                    process.nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS)
                elif nice in range(-20, -10):
                    self.message('Process Priority class: high')
                    process.nice(psutil.HIGH_PRIORITY_CLASS)
            else:
                process.nice(nice)
        except Exception as err:
            self.message(
                f'Could not apply limits to process {process.pid}: {err}')
            return False
        else:
            return True

    def stop(self):
        self.message('Stopping IPFS daemon')
        try:
            if not self.process:
                raise Exception('Process not found')

            if platform.system() == 'Windows':
                self.process.kill()
            else:
                self.process.send_signal(signal.SIGINT)
                self.process.send_signal(signal.SIGHUP)

            # Publish a pubsub event message notifying
            # that the daemon was stopped
            self.publishEvent({
                'type': 'IpfsDaemonStoppedEvent',
                'ipfsNetworkName': self.ipfsNetworkName,
                'ipfsNetworkUri': self.ipfsNetworkRunningUri
            })

            self._procPid = None
            return True
        except Exception as err:
            self.message(f'Error shutting down daemon: {err}')
            self._procPid = None
            self.terminateException = err
            return False
