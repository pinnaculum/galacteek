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
    async def nsToIpfs(self, ipfsop, ns: str) -> IPFSPath:
        """
        Translate an ips host name (for schemas) to a UnixFS
        object path.

        :param str ns: IPS host key
        """
        path = self._nsMappings.get(ns, None)
        if path:
            return path

        nsLocation = self._fallbackNs.get(ns, None)
        if nsLocation:
            dirp = nsLocation['root']

            cid = await self.importLdContexts(
                ipfsop,
                ns,
                dirp,
                ipfsIgnorePath=nsLocation['ipfsignore']
            )

            self._nsMappings[ns] = IPFSPath(cid)
            return self._nsMappings[ns]

    def discover(self):
        # TODO: move to config.yaml
        pkgList = [
            'galacteek-ld-web4'
        ]

        for p in pkgList:
            pName = p.replace('-', '_')
            ctxModPath = f'{pName}.contexts'

            try:
                for ename in pkgResourcesListDir(ctxModPath, ''):
                    if ename.startswith('_'):
                        continue

                    ipsRootPath = pkgResourcesRscFilename(ctxModPath, ename)
                    if not ipsRootPath:
                        continue

                    rootp = Path(ipsRootPath)
                    iip = rootp.joinpath('.ipfsignore')

                    self._fallbackNs[ename] = {
                        'ipfsignore': iip if iip.is_file() else None,
                        'root': rootp
                    }
            except Exception as err:
                log.debug(
                    f'Error discovering IPS schemas pkg ({p}): {err}')
                continue

    async def update(self, ipfsop):
        await self.nsToIpfs('galacteek.ld')

    async def importLdContexts(self,
                               ipfsop,
                               distName,
                               contextsPath,
                               ipfsIgnorePath: Path = None):
        """
        Import the JSON-LD contexts and associate the
        directory entry with the 'galacteek.ld' key
        """

        if not contextsPath.is_dir():
            log.debug('LD contexts not found')
            return

        log.debug(f'ips: LD import: {distName}')

        if ipfsIgnorePath:
            log.debug(f'ips: ({distName}): ipfsignore {ipfsIgnorePath}')

        entry = await ipfsop.addPath(
            str(contextsPath),
            recursive=True,
            hidden=False,
            ignRulesPath=str(ipfsIgnorePath) if ipfsIgnorePath else None
        )
        if entry:
            ldKeyName = distName
            ldCid = entry.get('Hash')

            log.debug(f'LD contexts ({ldKeyName}) sitting at: {ldCid}')

            ke = await ipfsop.keyFind(ldKeyName)
            if not ke:
                result = await ipfsop.keyGen(
                    ldKeyName,
                    checkExisting=False
                )

                if result is False:
                    log.debug(f'{ldKeyName}: key creation failed')
                    return None
                else:
                    log.debug(f'{ldKeyName}: key creation was successfull')

            ensure(ipfsop.publish(
                entry['Hash'],
                key=ldKeyName,
                allow_offline=True
            ))

            self._fsWatcherContexts.clear()
            self._fsWatcherContexts.watch(str(contextsPath))

            await ipfsop.sleep(0.1)

            return entry['Hash']

    def onLdContextsChanged(self, path):
        pass
