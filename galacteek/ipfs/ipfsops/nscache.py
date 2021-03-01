import json
import aiofiles
import asyncio
import time
from pathlib import Path

from galacteek import log
from galacteek.core import jsonSchemaValidate
from galacteek.config import cParentGet

from galacteek.ipfs.cidhelpers import joinIpns
from galacteek.ipfs.cidhelpers import stripIpns
from galacteek.ipfs.cidhelpers import ipnsKeyCidV1

ppRe = r"^(/ipns/[\w<>\:\;\,\?\!\*\%\&\=\@\$\~/\s\.\-_\\\'\(\)\+]{1,1024}$)"
nsCacheSchema = {
    "title": "NS cache",
    "description": "NS cache schema",
    "type": "object",
    "patternProperties": {
        ppRe: {
            "properties": {
                "resolved": {
                    "type": "string"
                },
                "resolvedLast": {
                    "type": "integer"
                },
                "cacheOrigin": {
                    "type": "string"
                }
            }
        }
    }
}


class IPNSCache:
    def __init__(self, path: Path):
        self.nsCachePath = path
        self._lock = asyncio.Lock()
        self.cache = {}

    @property
    def cNsCache(self):
        return cParentGet('nsCache')

    def nsCacheLoad(self):
        try:
            assert len(self.cache) == 0

            with open(str(self.nsCachePath), 'r') as fd:
                cache = json.load(fd)

            if not jsonSchemaValidate(cache, nsCacheSchema):
                raise Exception('Invalid NS cache schema')
        except Exception as err:
            log.debug(f'Error loading NS cache: {err}')
        else:
            log.warning(f'IPNS cache: loaded from {self.nsCachePath}')
            self.cache = cache

    async def nsCacheSave(self):
        if not self.nsCachePath or not isinstance(self.cache, dict):
            return

        async with self._lock:
            async with aiofiles.open(str(self.nsCachePath), 'w+t') as fd:
                await fd.write(json.dumps(self.cache))

    def nsCacheGet(self, path, maxLifetime=None, knownOrigin=False):
        entry = self.cache.get(path)

        if isinstance(entry, dict):
            rLast = entry['resolvedLast']

            if knownOrigin is True and entry.get('cacheOrigin') == 'unknown':
                return None

            if not maxLifetime or (int(time.time()) - rLast) < maxLifetime:
                return entry['resolved']

    async def nsCacheSet(self, path, resolved, origin=None):
        self.cache[path] = {
            'resolved': resolved,
            'resolvedLast': int(time.time()),
            'cacheOrigin': origin
        }

        # Cache v1
        v1 = ipnsKeyCidV1(stripIpns(path))
        if v1:
            self.cache[joinIpns(v1)] = {
                'resolved': resolved,
                'resolvedLast': int(time.time()),
                'cacheOrigin': origin
            }

        await self.nsCacheSave()
