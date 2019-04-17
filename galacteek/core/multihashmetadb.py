import asyncio
import aiofiles
import os.path
import os
import json

from galacteek import log
from galacteek.ipfs.cidhelpers import stripIpfs
from galacteek.ipfs.cidhelpers import isIpfsPath


class IPFSObjectMetadataDatabase:
    """
    Basic file-based database to hold metadata about IPFS objects by path
    """

    def __init__(self, metaDbPath):
        super().__init__()

        self._metaDbPath = metaDbPath
        self._lock = asyncio.Lock()

    @property
    def metaDbPath(self):
        return self._metaDbPath

    async def path(self, rscPath):
        with await self._lock:
            if isinstance(rscPath, str) and isIpfsPath(rscPath):
                path = stripIpfs(
                    rscPath.rstrip('/')).replace('/', '_')
                comps = path.split('/')

                if len(comps) > 0:
                    containerId = comps[0][0:8]
                    containerPath = os.path.join(self.metaDbPath, containerId)
                    metaPath = os.path.join(containerPath, path)
                    return containerPath, metaPath, os.path.exists(metaPath)

        return None, None, False

    async def store(self, rscPath, mimeType, statInfo):
        containerPath, metaPath, exists = await self.path(rscPath)
        if metaPath and not exists:
            if not os.path.isdir(containerPath):
                os.mkdir(containerPath)
            with await self._lock:
                try:
                    async with aiofiles.open(metaPath, 'w+t') as fd:
                        await fd.write(
                            json.dumps({
                                'mimetype': mimeType,
                                'stat': statInfo
                            }, indent=4)
                        )
                except BaseException:
                    log.debug('Error storing metadata for {0}'.format(
                        rscPath))

    async def get(self, rscPath):
        containerPath, metaPath, exists = await self.path(rscPath)
        if metaPath and exists:
            with await self._lock:
                try:
                    async with aiofiles.open(metaPath, 'rt') as fd:
                        data = await fd.read()
                        return json.loads(data)
                except BaseException as err:
                    # Error reading metadata
                    log.debug('Error reading rscPath info for {0}: {1}'.format(
                        rscPath, str(err)))
                    os.unlink(metaPath)
