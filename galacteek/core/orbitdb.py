import os
import os.path
import asyncio
import json
import inspect
import collections
import uuid

import aiohttp
from yarl import URL

from PyQt5.QtCore import QObject, pyqtSignal

from galacteek import log, ensure


class OrbitConnectorProtocol(asyncio.SubprocessProtocol):
    def __init__(self):
        self._output = bytearray()
        self.evStarted = asyncio.Event()
        self.evExited = asyncio.Event()
        self.eventsQueue = asyncio.Queue(maxsize=256)

    @property
    def output(self):
        return self._output

    def pipe_data_received(self, fd, data):
        try:
            msg = data.decode().strip()
        except BaseException:
            return

        for line in msg.split('\n'):
            try:
                obj = json.loads(line)
                ensure(self.eventsQueue.put(obj))
            except BaseException:
                log.debug('Orbit connector unknown output: {0}'.format(line))
            else:
                log.debug('Orbit connector event: {0}'.format(obj))

                if 'servicestatus' in obj:
                    if obj['servicestatus'] == 'running':
                        self.evStarted.set()
                    else:
                        self.evExited.set()

        self._output.extend(data)

    def process_exited(self):
        self.evExited.set()


class NodeOrbitProcess(object):
    def __init__(
            self,
            port=3000,
            orbitDataPath='/tmp',
            ipfsApiHost='localhost',
            ipfsApiPort=5001):
        self.loop = asyncio.get_event_loop()
        self.port = port
        self.ipfsApiHost = ipfsApiHost
        self.ipfsApiPort = ipfsApiPort
        self.orbitDataPath = orbitDataPath

    async def start(self):
        here = os.path.realpath(
            os.path.abspath(
                os.path.split(
                    inspect.getfile(
                        inspect.currentframe()))[0]))
        root = os.path.join(here, '..', '..', 'galacteek-orbital-service')

        args = ['node', os.path.join(root, 'galacteek-orbital.js')]

        args += [
            '--ipfsapihost',
            self.ipfsApiHost
        ]
        args += [
            '--ipfsapiport',
            str(self.ipfsApiPort)
        ]

        args += [
            '--serviceport',
            str(self.port)
        ]

        args += [
            '--orbitdatapath',
            str(self.orbitDataPath)
        ]

        f = self.loop.subprocess_exec(
            lambda: OrbitConnectorProtocol(),
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=None)
        self.transport, self.proto = await f
        return True

    def stop(self):
        try:
            self.transport.terminate()
            return True
        except Exception as e:
            self.terminateException = e
            return False


class ConfigMapNotifier(QObject):
    changed = pyqtSignal()


class OrbitConfigMap(collections.UserDict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mapName = kwargs.pop('name', str(uuid.uuid4())),
        self.notifier = ConfigMapNotifier(None)

    def __str__(self):
        return json.dumps(self.data, indent=4)

    @property
    def mapName(self):
        return self._mapName

    @property
    def json(self):
        return self.data

    def hasDatabase(self, ns, dbname):
        namespaces = self.data.setdefault('namespaces', {})
        if ns in namespaces:
            return dbname in namespaces[ns]
        return False

    def newDatabase(self, ns, dbname, dbtype, load=-1, dbuuid=None,
                    write=None, address=None, create=True):
        if self.hasDatabase(ns, dbname):
            return
        namespaces = self.data.setdefault('namespaces', {})
        if ns not in namespaces:
            namespaces[ns] = {}
        namespaces[ns][dbname] = {
            'uuid': dbuuid if dbuuid else str(uuid.uuid4()),
            'address': address,
            'type': dbtype,
            'load': load,
            'write': write,
            'create': create
        }
        self.notifier.changed.emit()


class DatabaseOperator:
    def __init__(self, ns, dbname, connector, dbtype='eventlog'):
        self.ns = ns
        self.dbname = dbname
        self.connector = connector
        self.dbtype = dbtype

    def __str__(self):
        return 'Database @{0}/{1}'.format(self.ns, self.dbname)

    async def create(self):
        return await self.connector.createdb(self.ns, self.dbname, self.dbtype)

    async def list(self, *args, **kw):
        return await self.connector.list(self.ns, self.dbname, *args, **kw)

    async def putdoc(self, *args, **kw):
        return await self.connector.putdoc(self.ns, self.dbname, *args, **kw)

    async def get(self, *args, **kw):
        return await self.connector.get(self.ns, self.dbname, *args, **kw)

    async def set(self, *args, **kw):
        return await self.connector.set(self.ns, self.dbname, *args, **kw)

    async def add(self, *args, **kw):
        return await self.connector.add(self.ns, self.dbname, *args, **kw)

    async def open(self, *args, **kw):
        resp = await self.connector.request(self.connector.endpoint(
            os.path.join(self.ns, self.dbname, 'open')))
        if resp and resp['status'] == 'success':
            return True
        return False


class OrbitConnector:
    def __init__(self, orbitDataPath='/tmp',
                 servicePort=3000):
        self.servicePort = servicePort
        self.orbitDataPath = orbitDataPath
        self._connected = False
        self.eventListeners = []
        self._configMaps = {}

    @property
    def connected(self):
        return self._connected

    def registerEventListener(self, coro):
        self.eventListeners.append(coro)

    def useConfigMap(self, cfgMap):
        self._configMaps[cfgMap.mapName] = cfgMap

    async def syncConfig(self):
        pass

    async def start(self, servicePort=None):
        if self.connected:
            return True

        port = servicePort if servicePort else self.servicePort

        self.commandsQ = asyncio.Queue()
        self.servicePort = servicePort
        self.process = NodeOrbitProcess(port=port,
                                        orbitDataPath=self.orbitDataPath)
        self.baseUrl = URL.build(scheme='http', host='localhost',
                                 port=port)
        await self.process.start()

        try:
            await asyncio.wait_for(
                self.process.proto.evStarted.wait(),
                60)
        except asyncio.TimeoutError:
            log.debug('Time out while waiting for connector to rise')
            return False

        await asyncio.sleep(0.5)

        ensure(self.readEventsTask(self.process.proto))

        self._connected = True
        return True

    async def readEventsTask(self, protocol):
        while True:
            item = await protocol.eventsQueue.get()
            if not isinstance(item, dict):
                continue

            for listener in self.eventListeners:
                await listener(item)

    async def queueCommand(self, ns, dbname, cmd):
        await self.commandsQ.put({
            'namespace': ns,
            'dbname': dbname,
            'command': cmd
        })

    async def wsListenEvents(self):
        url = self.endpoint('status')
        async with aiohttp.ClientSession() as sess:
            async with sess.ws_connect(url, autoping=False) as ws:
                while True:
                    cmd = await self.commandsQ.get()
                    await ws.send_json(cmd)
                    reply = await ws.receive_json()
                    log.debug('WS ORBIT REPLY {0}'.format(reply))

    def endpoint(self, path):
        return str(self.baseUrl.join(URL(path)))

    async def stop(self):
        await self.request('disconnect')
        self.process.stop()

    async def request(self, path, method='get', params=None):
        try:
            async with aiohttp.ClientSession() as sess:
                meth = getattr(sess, method)
                if meth is None:
                    return None
                async with meth(self.endpoint(path), params=params) as resp:
                    return await resp.json()
        except BaseException:
            log.debug('Error when running request: {path}'.format(
                path=path))

    async def getconfig(self):
        return await self.request('getconfig')

    async def publicKey(self):
        resp = await self.request('publicKey')
        if resp['status'] == 'success':
            return resp['key']

    async def reconfigure(self):
        for mapName, cfgMap in self._configMaps.items():
            try:
                await self.configure(cfgMap.json)
            except BaseException:
                log.debug('Error mapping orbit config')
                continue
            else:
                log.debug('Mapped {name}'.format(name=mapName))

    async def configure(self, config):
        async with aiohttp.ClientSession() as sess:
            log.debug('Configuring orbit with {cfg}'.format(cfg=config))
            async with sess.post(self.endpoint('map'),
                                 json=config) as resp:
                reply = await resp.json()
                log.debug('Orbit service configure reply: {0}'.format(reply))

    map = configure

    async def list(self, ns, dbname, reverse=True, limit=-1):
        params = {
            'limit': limit
        }
        if reverse:
            params['reverse'] = 1

        resp = await self.request(self.endpoint(
            os.path.join(ns, dbname, 'list')),
            params=params)

        if resp['status'] == 'success':
            return resp['value']

        async with aiohttp.ClientSession() as sess:
            async with sess.get(self.endpoint(
                os.path.join(ns, dbname, 'list')),
                    params=params) as resp:
                reply = await resp.json()
                return reply

    async def query(self, ns, dbname, text):
        async with aiohttp.ClientSession() as sess:
            async with sess.get(self.endpoint(
                os.path.join(ns, dbname, 'query')),
                    params={'search': text}) as resp:
                reply = await resp.json()
                return reply

    async def get(self, ns, dbname, key):
        async with aiohttp.ClientSession() as sess:
            async with sess.get(self.endpoint(
                    os.path.join(ns, dbname, 'get')),
                    params={'key': key}) as resp:
                result = await resp.json()
                if result['status'] == 'success' and 'value' in result:
                    return result['value']

    async def add(self, ns, dbname, value):
        async with aiohttp.ClientSession() as sess:
            async with sess.post(self.endpoint(
                    os.path.join(ns, dbname, 'add')), json=value) as resp:
                reply = await resp.json()
                return reply

    async def putdoc(self, ns, dbname, data):
        async with aiohttp.ClientSession() as sess:
            async with sess.post(self.endpoint(
                    os.path.join(ns, dbname, 'put')), json=data) as resp:
                reply = await resp.json()
                return reply

    async def set(self, ns, dbname, key, value):
        async with aiohttp.ClientSession() as sess:
            async with sess.post(self.endpoint(
                    os.path.join(ns, dbname, 'set')),
                    json={'key': key, 'value': value}) as resp:
                reply = await resp.json()
                return reply

    async def createdb(self, ns, dbname, dbtype, params={}):
        resp = await self.request(self.endpoint(
            os.path.join(ns, dbname, 'createdb')), method='post')
        if resp and resp['status'] == 'success':
            return resp['address']

    def database(self, ns, dbname, dbtype='eventlog'):
        return DatabaseOperator(ns, dbname, self, dbtype=dbtype)


class GalacteekOrbitConnector(OrbitConnector):
    def __init__(self, orbitDataPath='/tmp',
                 servicePort=3000):
        super(GalacteekOrbitConnector, self).__init__(
            orbitDataPath=orbitDataPath,
            servicePort=servicePort)

        self.dbUsernames = self.database('core', 'usernames',
                                         dbtype='eventlog')

    async def start(self, servicePort=None):
        resp = await super(GalacteekOrbitConnector, self).start(
            servicePort=servicePort)
        ensure(self.dbUsernames.open())
        return resp

    async def usernamesList(self):
        resp = await self.dbUsernames.list()
        if resp:
            usernames = [elem['value']['name'] for elem in resp]
        else:
            usernames = []
        return usernames
