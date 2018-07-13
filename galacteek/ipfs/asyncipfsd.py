
import os, os.path
import sys
import asyncio
import tempfile
import functools
import re
import json

async def shell(arg):
    p = await asyncio.create_subprocess_shell((arg),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE)

    stdout, stderr = await p.communicate()
    return stdout.decode()

async def exec(*args, **kw):
    return await asyncio.create_subprocess_exec(*args, **kw)

async def ipfsConfig(param, value):
    return await shell("ipfs config '{0}' '{1}'".format(param, value))

async def ipfsConfigJson(param, value):
    return await shell('ipfs config --json {0} {1}'.format(
        param, json.dumps(value)))

async def ipfsConfigGetJson(param):
    return await shell('ipfs config --json "{0}"'.format(param))

class IPFSDProtocol(asyncio.SubprocessProtocol):
    # This handles output from the IPFS daemon
    # Mainly used to more finely monitor the process and know when the various
    # subsystems have been started

    def __init__(self, exitFuture, startedFuture, debug=True):
        self.debug = debug
        self.exitFuture = exitFuture
        self.startedFuture = startedFuture
        self.output = bytearray()
        self.apiStarted = False
        self.gatewayStarted = False
        self.swarmStarted = False
        self.daemonReady = False
        self.errAlreadyRunning = False

    def pipe_data_received(self, fd, data):
        try:
            msg = data.decode().strip()
        except:
            return

        # The output we expect might be different in earlier versions
        # i've mainly tested with go-ipfs > 0.4.11
        # TODO: implement ipfs process supervisor independent of daemon output

        for line in msg.split('\n'):
            if self.debug:
                print(line, file=sys.stderr)
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

        self.output.extend(data)

    def process_exited(self):
        self.exitFuture.set_result(True)

DEFAULT_APIPORT = 5001
DEFAULT_SWARMPORT = 4001
DEFAULT_GWPORT = 8080

class AsyncIPFSDaemon(object):
    def __init__(self, repopath, apiport=DEFAULT_APIPORT,
            swarmport=DEFAULT_SWARMPORT,
            gatewayport=DEFAULT_GWPORT, initrepo=True,
            swarmLowWater=10, swarmHighWater=20,
            pubsubEnable=False, noBootstrap=False, corsEnable=True,
            storageMax=20, debug=False, loop=None):

        self.loop = loop if loop else asyncio.get_event_loop()
        self.repopath = repopath
        self.apiport = apiport
        self.gatewayport = gatewayport
        self.swarmport = swarmport
        self.swarmLowWater = swarmLowWater
        self.swarmHighWater = swarmHighWater
        self.storageMax = storageMax
        self.initrepo = initrepo
        self.pubsubEnable = pubsubEnable
        self.corsEnable = corsEnable
        self.noBootstrap = noBootstrap
        self.debug = debug

    async def start(self):
        # Sets the IPFS_PATH environment variable
        os.putenv('IPFS_PATH', self.repopath)
        if not os.path.isdir(self.repopath):
            os.mkdir(self.repopath)

        if not os.path.exists(os.path.join(self.repopath, 'config')) or \
            not os.path.isdir(os.path.join(self.repopath, 'datastore')):
            # Pretty sure this is an empty repository path
            initOutput = await shell('ipfs init')

        # Change the addresses/ports we listen on
        await ipfsConfig('Addresses.API',
                '/ip4/127.0.0.1/tcp/{0}'.format(self.apiport))
        await ipfsConfig('Addresses.Gateway',
                '/ip4/127.0.0.1/tcp/{0}'.format(self.gatewayport))
        await ipfsConfigJson('Addresses.Swarm',
                '["/ip4/0.0.0.0/tcp/{0}"]'.format(self.swarmport))

        # Swarm connection manager parameters
        await ipfsConfigJson('Swarm.ConnMgr.LowWater', self.swarmLowWater)
        await ipfsConfigJson('Swarm.ConnMgr.HighWater', self.swarmHighWater)

        # Maximum storage
        await ipfsConfig('Datastore.StorageMax',
                '{0}GB'.format(self.storageMax))

        # CORS
        if self.corsEnable:
            # Setup the CORS headers, only allowing the gateway's origin
            await ipfsConfigJson(
                    'API.HTTPHeaders.Access-Control-Allow-Credentials',
                    '["true"]')
            await ipfsConfigJson(
                    'API.HTTPHeaders.Access-Control-Allow-Origin',
                    '["http://localhost:{0}"]'.format(self.gatewayport))

        if self.noBootstrap:
            await ipfsConfigJson('Bootstrap', '[]')

        exitFuture = asyncio.Future(loop=self.loop)
        startedFuture = asyncio.Future(loop=self.loop)
        args = ['ipfs', 'daemon']

        if self.pubsubEnable:
            args.append('--enable-pubsub-experiment')

        f = self.loop.subprocess_exec(
                lambda: IPFSDProtocol(exitFuture, startedFuture,
                    debug=self.debug),
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE)
        self.transport, self.proto = await f
        return True

    def stop(self):
        try:
            self.transport.terminate()
            return True
        except Exception as e:
            self.terminateException = e
            return False
