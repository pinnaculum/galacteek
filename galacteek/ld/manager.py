from pathlib import Path

from galacteek import log
from galacteek import ensure

from galacteek.ipfs import ipfsOp
from galacteek.ipfs.cidhelpers import IPFSPath

from galacteek.core import pkgResourcesRscFilename
from galacteek.core import pkgResourcesListDir
from galacteek.core.fswatcher import FileWatcher


class LDSchemasImporter:
    def __init__(self):
        self._fsWatcherContexts = FileWatcher()
        self._fsWatcherContexts.pathChanged.connect(
            self.onLdContextsChanged)

        self._fallbackNs = {}

        # NS <=> IPFS paths mapping
        self._nsMappings = {}

    @ipfsOp
    async def nsToIpfs(self, ipfsop, ns) -> IPFSPath:
        path = self._nsMappings.get(ns, None)
        if path:
            return path

        spath = self._fallbackNs.get(ns, None)
        if spath:
            cid = await self.importLdContexts(
                ipfsop,
                ns,
                spath
            )

            self._nsMappings[ns] = IPFSPath(cid)
            return self._nsMappings[ns]

    def discover(self):
        pkgList = [
            'galacteek-ld-web4'
        ]

        for p in pkgList:
            pName = p.replace('-', '_')
            ctxModPath = f'{pName}.contexts'

            for ename in pkgResourcesListDir(ctxModPath, ''):
                if ename.startswith('_'):
                    continue

                epath = pkgResourcesRscFilename(ctxModPath, ename)
                if not epath:
                    continue

                self._fallbackNs[ename] = Path(epath)

    async def update(self, ipfsop):
        await self.nsToIpfs('galacteek.ld')

    async def importLdContexts(self,
                               ipfsop,
                               distName,
                               contextsPath):
        """
        Import the JSON-LD contexts and associate the
        directory entry with the 'galacteek.ld' key
        """

        if not contextsPath.is_dir():
            log.debug('LD contexts not found')
            return

        entry = await ipfsop.addPath(
            str(contextsPath),
            recursive=True,
            hidden=False
        )
        if entry:
            ldKeyName = distName

            log.debug('LD contexts sitting at: {}'.format(
                entry.get('Hash')))
            print('LD contexts sitting at: {}'.format(
                entry.get('Hash')))

            ke = await ipfsop.keyFind(ldKeyName)
            if not ke:
                await ipfsop.keyGen(
                    ldKeyName,
                    checkExisting=False
                )

            ensure(ipfsop.publish(
                entry['Hash'],
                key=ldKeyName,
                allow_offline=True
            ))

            if 0:
                await ipfsop.publish(
                    entry['Hash'],
                    key=ldKeyName,
                    allow_offline=True
                )

            self._fsWatcherContexts.clear()
            self._fsWatcherContexts.watch(str(contextsPath))

            await ipfsop.sleep(0.5)

            return entry['Hash']

    def onLdContextsChanged(self, path):
        ensure(self.update())
