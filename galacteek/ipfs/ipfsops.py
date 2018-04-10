
import sys
import os.path

import aioipfs

GFILES_ROOT_PATH = '/galacteek/'
GFILES_MYFILES_PATH = os.path.join(GFILES_ROOT_PATH, 'myfiles')
GFILES_WEBSITES_PATH = os.path.join(GFILES_ROOT_PATH, 'websites')

def joinIpfs(hash):
    return os.path.join('/ipfs/', hash)

class IPFSOperator(object):
    def __init__(self, client, debug=False):
        self.client = client
        self.debugInfo = debug

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
