from pathlib import Path
from urllib.parse import urlparse

from galacteek import log
from galacteek.core import SingletonDecorator
from galacteek.core.tmpf import TmpDir
from galacteek.core.asynclib import asyncWriteFile
from galacteek.ipfs import ipfsOp
from galacteek.ipfs import posixIpfsPath


try:
    from magnet2torrent import Magnet2Torrent, FailedToFetchException
except ImportError:
    haveMagnet2torrent = False
else:
    haveMagnet2torrent = True


def isMagnetLink(link: str):
    return urlparse(link).scheme == 'magnet'


@SingletonDecorator
class IPFSMagnetConvertor:
    @property
    def available(self):
        return haveMagnet2torrent

    async def toTorrentData(self, magnetLink):
        m2t = Magnet2Torrent(magnetLink)
        try:
            filename, torrentData = await m2t.retrieve_torrent()
        except FailedToFetchException as err:
            log.debug(f'Failed to fetch magnet: {err}')
            return None, None
        else:
            log.debug(f'Magnet fetch OK: {magnetLink}, filename is {filename}')
            return filename, torrentData

    @ipfsOp
    async def toIpfs(self, ipfsop, magnetLink):
        filename, data = await self.toTorrentData(magnetLink)

        if not filename:
            return None, None

        entry = None

        try:
            with TmpDir() as tmpdir:
                tmpPath = Path(tmpdir)
                torrentPath = tmpPath.joinpath(filename)

                # Write the torrent file in the tmpdir
                await asyncWriteFile(str(torrentPath), data)

                # Add the directory, asking for the entry of torrent file
                # and not the wrapper directory

                entry = await ipfsop.addPath(tmpdir)

                if 0:
                    entry = await ipfsop.addPath(
                        tmpdir,
                        rEntryFilePath=posixIpfsPath.join(
                            tmpPath.name,
                            filename
                        )
                    )
            if entry:
                log.debug(f'Magnet ({magnetLink}) to IPFS: {entry}')
                return entry['Hash'], filename
            else:
                raise Exception('Could not add entry')
        except Exception as err:
            log.debug(f'Magnet to torrent failed: {err}')
            return None, None
