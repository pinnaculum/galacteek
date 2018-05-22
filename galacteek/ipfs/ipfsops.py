
import sys
import os.path

from async_generator import async_generator, yield_

import aioipfs
import asyncio

GFILES_ROOT_PATH = '/galacteek/'
GFILES_MYFILES_PATH = os.path.join(GFILES_ROOT_PATH, 'myfiles')
GFILES_WEBSITES_PATH = os.path.join(GFILES_ROOT_PATH, 'websites')

def joinIpfs(path):
    return os.path.join('/ipfs/', path)

def joinIpns(path):
    return os.path.join('/ipns/', path)

class IPFSLogWatcher(object):
    def __init__(self, operator):
        self.op = operator

    async def analyze(self):
        import pprint
        async for msg in self.op.client.log.tail():
            event = msg.get('event', None)
            time = msg.get('time', None)

            if not event:
                continue

            if event == 'handleAddProvider':
                # Handle add provider
                if self.op.ctx:
                    self.op.ctx.logAddProvider.emit(msg)

class IPFSOperator(object):
    def __init__(self, client, ctx=None, debug=False):
        self.client = client
        self.debugInfo = debug
        self.ctx = ctx

    async def sleep(self, t=0):
        await asyncio.sleep(t)

    @property
    def logwatch(self):
        return IPFSLogWatcher(self)

    def debug(self, msg):
        if self.debugInfo:
            print(msg, file=sys.stderr)

    async def filesDelete(self, path, name, recursive=False):
        try:
            ret = await self.client.files.rm(os.path.join(path, name),
                    recursive=recursive)
        except aioipfs.APIException as exc:
            self.debug('Exception on removing {0} in {1}'.format(
                name, path))
            return False
        await self.client.files.flush(path)
        return True

    async def filesLookup(self, path, name):
        listing = await self.filesList(path)
        for entry in listing:
            if entry['Name'] == name:
                return entry

    async def filesLookupHash(self, path, hash):
        listing = await self.filesList(path)
        for entry in listing:
            if entry['Hash'] == hash:
                return entry

    async def filesList(self, path):
        try:
            listing = await self.client.files.ls(path, long=True)
        except aioipfs.APIException as exc:
            self.debug(exc.message)
            return None

        if not 'Entries' in listing or listing['Entries'] is None:
            return []

        return listing['Entries']

    async def filesLink(self, entry, dest, flush=True, name=None):
        """ Given an entry (as returned by /files/ls), make a link
            in dest """

        try:
            resp = await self.client.files.cp(joinIpfs(entry['Hash']),
                os.path.join(dest, name if name else entry['Name']))
        except aioipfs.APIException as exc:
            self.debug('Exception on copying entry {0} to {1}'.format(
                entry, dest))
            return False

        if flush:
            await self.client.files.flush(dest)
        return True

    async def peersList(self):
        try:
            peers = await self.client.swarm.peers()
        except aioipfs.APIException as exc:
            return None

        if peers and 'Peers' in peers:
            return peers.get('Peers', None)

    async def nodeId(self):
        info = await self.client.core.id()
        return info.get('ID', 'Unknown')

    async def keysNames(self):
        keys = await self.keys()
        return [key['Name'] for key in keys]

    async def keys(self):
        kList = await self.client.key.list(long=True)
        return kList.get('Keys', [])

    async def keysRemove(self, name):
        try:
            await self.client.key.rm(name)
        except aioipfs.APIException as exc:
            self.debug('Exception on removing key {0}: {1}'.format(
                name, exc.message))
            return False
        return True

    async def publish(self, path, key='self'):
        try:
            return await self.client.name.publish(path, key=key)
        except aioipfs.APIException as exc:
            return None

    async def resolve(self, path):
        try:
            return await self.client.name.resolve(path)
        except aioipfs.APIException as e:
            return None

    async def purge(self, hashRef, rungc=False):
        """ Unpins an object and optionally runs the garbage collector """
        try:
            await self.client.pin.rm(hashRef, recursive=True)
            if rungc:
                await self.client.repo.gc()
            return True
        except aioipfs.APIException as e:
            return False

    async def isPinned(self, hashRef):
        """
        Returns True if IPFS object references by hashRef is pinned,
        False otherwise
        """
        try:
            result = await self.client.pin.ls(multihash=hashRef)
            keys = result.get('Keys', {})
            return key in keys
        except aioipfs.APIException as e:
            return False

    async def pinned(self, type='all'):
        """
        Returns all pinned keys of a given type
        """
        try:
            result = await self.client.pin.ls(pintype=type)
            return result.get('Keys', {})
        except aioipfs.APIException as e:
            return None

    @async_generator
    async def list(self, path):
        """
        Lists objects in path and yields them
        """
        try:
            listing = await self.client.ls(path, headers=True)
            objects = listing.get('Objects', [])

            for obj in objects:
                await yield_(obj)
        except:
            pass

    async def objStat(self, path):
        return await self.client.object.stat(path)

    async def objStatCtxUpdate(self, path):
        try:
            self.ctx.objectStats[path] = await self.objStat(path)
            return self.ctx.objectStats[path]
        except aioipfs.APIException as e:
            self.ctx.objectStats[path] = None

    def objStatCtxGet(self, path):
        return self.ctx.objectStats.get(path, None)

    async def addPath(self, path, **kw):
        """
        Recursively adds files from path, and returns the top-level entry (the
        root directory), optionally wrapping it with a directory object

        :param str path: the path to the directory/file to import
        :param bool wrap: add a wrapping directory
        :return: the IPFS top-level entry
        :rtype: dict
        """
        added = None
        entryCb = kw.pop('callback', None)
        async for entry in self.client.add(path, quiet=True,
                recursive=kw.pop('recursive', True),
                wrap_with_directory=kw.pop('wrap', False)):
            await self.sleep()
            added = entry
            if asyncio.iscoroutinefunction(entryCb):
                await entryCb(entry)
        return added

    async def closestPeers(self):
        peers = []
        try:
            info = await self.client.core.id()
            queryR = await self.client.dht.query(info['ID'])

            responses = queryR.get('Responses', None)
            if not responses:
                return None
            for resp in responses:
                peers.append(resp['ID'])
            return peers
        except aioipfs.APIException as e:
            return None
