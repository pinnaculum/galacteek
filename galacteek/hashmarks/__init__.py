import asyncio
import tempfile
import shutil
import tarfile
import os
from pathlib import Path
from datetime import datetime
from yaml import load

from galacteek import log
from galacteek import AsyncSignal
from galacteek import database
from galacteek.database.models import *
from galacteek.core import utcDatetimeIso
from galacteek.core import jsonSchemaValidate
from galacteek.core import SingletonDecorator
from galacteek.core import pkgResourcesListDir
from galacteek.core import pkgResourcesRscFilename
from galacteek.core.iptags import ipTagRe
from galacteek.core.ipfsmarks import IPFSMarks
from galacteek.core.asynclib.fetch import httpFetch


try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader


schema = {
    'title': 'Hashmarks collection',
    'type': 'object',
    'properties': {
        'hashmarks': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'url': {
                        'type': 'string',
                        'minLength': 2,
                        'maxLength': 512
                    },
                    'title': {
                        'type': 'string',
                        'minLength': 2,
                        'maxLength': 128
                    },
                    'description': {
                        'type': 'string',
                        'minLength': 2,
                        'maxLength': 512
                    },
                    'comment': {
                        'type': 'string',
                        'minLength': 2,
                        'maxLength': 1024
                    },
                    'icon': {
                        'type': 'string',
                        'minLength': 2,
                        'maxLength': 128
                    },
                    'category': {
                        'type': 'string',
                        'minLength': 2,
                        'maxLength': 64,
                        'pattern': r'[a-zA-Z0-9/]'
                    },
                    'datecreated': {
                        'type': 'string',
                        'format': 'date-time'
                    },
                    'schemepreferred': {
                        'type': 'string',
                        'pattern': r'(dweb|ipfs|ens)'
                    },
                    'tags': {
                        'type': 'array',
                        'items': {
                            'type': 'string',
                            'pattern': ipTagRe,
                        }
                    },
                    'objtags': {
                        'type': 'array',
                        'items': {
                            'type': 'string',
                            'pattern': ipTagRe
                        }
                    }
                },
                'required': ['url', 'title']
            }
        }
    }
}


sourceInfoSchema = {
    'title': 'Source infos',
    'type': 'object',
    'properties': {
        'source_name': {'type': 'string'},
        'source_uuid': {
            'type': 'string',
            'pattern': '[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}'
                       '-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}'
        },
        'source_author': {'type': 'string'}
    },
    'required': ['source_name']
}


async def importHashmark(mark, source):
    url = mark.get('url')
    datecreated = mark.get('datecreated', utcDatetimeIso())

    # log.debug('Importing {u} ({date})'.format(
    #     u=url, date=datecreated))

    return await database.hashmarkAdd(
        url,
        title=mark.get('title'),
        description=mark.get('description'),
        comment=mark.get('comment'),
        category=mark.get('category'),
        icon=mark.get('icon'),
        datecreated=datecreated,
        tags=mark.get('tags', []),
        objtags=mark.get('objtags', []),
        source=source,
        schemepreferred=mark.get('schemepreferred')
    )


class HashmarksCatalogLoader:
    async def updateSourceInfo(self, yamlpath: str, source):
        try:
            with open(yamlpath, 'rt') as fd:
                data = load(fd, Loader=Loader)
        except Exception as e:
            log.debug('Error importing {}: {}'.format(
                yamlpath, str(e)))
        else:
            if not jsonSchemaValidate(data, sourceInfoSchema):
                return False

            name = data.get('source_name')
            author = data.get('source_author')

            if not source.name:
                source.name = name

            source.author = author
            try:
                await source.save()
            except Exception:
                pass

            return True

    async def importYamlHashmarks(self, yamlpath, source):
        count = 0
        try:
            with open(yamlpath, 'rt') as fd:
                data = load(fd, Loader=Loader)
        except Exception as e:
            log.debug('Error importing {}: {}'.format(
                yamlpath, str(e)))

            return False

        if not jsonSchemaValidate(data, schema):
            return False

        for mark in data['hashmarks']:
            if await importHashmark(mark, source):
                count += 1

        return count

    async def load(self, url):
        pass


@SingletonDecorator
class ModuleCatalogLoader(HashmarksCatalogLoader):
    async def load(self, source):
        try:
            count = 0
            listing = pkgResourcesListDir(source.url, '')

            for fn in listing:
                if not fn.endswith('.yaml'):
                    continue

                path = pkgResourcesRscFilename(source.url, fn)
                count += await self.importYamlHashmarks(path, source)

            return count
        except Exception as e:
            log.debug(str(e))
            return 0


@SingletonDecorator
class GitCatalogLoader(HashmarksCatalogLoader):
    async def load(self, source):
        from git.repo import base
        from git.exc import InvalidGitRepositoryError

        loop = asyncio.get_event_loop()

        dstdir = tempfile.mkdtemp(prefix='githashmarks')

        if not dstdir:
            return False

        try:
            repo = await loop.run_in_executor(
                None, base.Repo.clone_from, source.url, dstdir)
        except InvalidGitRepositoryError:
            return messageBox(iGitInvalid())
        except Exception as e:
            log.debug(str(e))
            return -1
        else:
            tree = repo.tree()

            if 'hashmarks' not in tree:
                return -1

            if 'infos.yaml' in tree:
                await self.updateSourceInfo(
                    tree['infos.yaml'].abspath, source)

            for entry in tree['hashmarks']:
                if entry.name.endswith('.yaml'):
                    count = await self.importYamlHashmarks(
                        entry.abspath, source)

            shutil.rmtree(dstdir)
            return count


@SingletonDecorator
class YAMLArchiveLoader(HashmarksCatalogLoader):
    async def load(self, source):
        loop = asyncio.get_event_loop()

        tarfp, _sum = await httpFetch(source.url)

        if not tarfp:
            return False

        def extract(fp: str):
            try:
                dst = tempfile.mkdtemp(prefix='yaml_hashmarks_')

                tar = tarfile.open(fp)
                tar.extractall(dst)
                tar.close()
            except Exception as err:
                log.debug(f'YAMLArchiveLoader extract error: {err}')
            else:
                return Path(dst)

        try:
            dstdir = await loop.run_in_executor(
                None, extract, str(tarfp))
            assert dstdir is not None

            tarfp.unlink()
        except Exception as err:
            log.debug(f'YAMLArchiveLoader extract error: {err}')
            return -1
        else:
            count = 0
            infosp = dstdir.joinpath('infos.yaml')

            if infosp.is_file():
                if await self.updateSourceInfo(
                        str(infosp), source) is True:
                    log.debug(f'YAMLArchiveLoader ({source.url}) :'
                              'Updated source infos')

            for root, dirs, files in os.walk(
                    str(dstdir.joinpath('hashmarks'))):
                rootp = Path(root)

                for file in files:
                    if file.endswith('.yaml'):
                        path = str(rootp.joinpath(file))
                        c = await self.importYamlHashmarks(path, source)

                        if c > 0:
                            count += c

            shutil.rmtree(dstdir)
            log.debug(f'YAMLArchiveLoader ({source.url}): '
                      f'Loaded {count} hashmarks')
            return count


@ SingletonDecorator
class IPFSMarksCatalogLoader(HashmarksCatalogLoader):
    """
    Loads hashmarks from legacy ipfsmarks JSON files
    """

    async def load(self, source):
        try:
            count = 0

            marks = IPFSMarks(source.url, autosave=False)
            categories = marks.getCategories()

            for category in categories:
                mItems = marks.getCategoryMarks(category).items()

                for path, mark in mItems:
                    iPath = IPFSPath(path, autoCidConv=True)
                    if not iPath.valid:
                        continue

                    meta = mark.get('metadata')
                    tags = mark.get('tags')

                    log.debug(
                        'Importing hashmark from ipfsmarks file: {}'.format(
                            path))

                    if isinstance(tags, list):
                        taglist = ['#' + tag for tag in tags]
                    else:
                        taglist = None

                    if await database.hashmarkAdd(
                        str(iPath),
                        category=category,
                        title=meta.get('title'),
                        description=meta.get('description'),
                        comment=mark['metadata'].get('comment'),
                        icon=mark.get('icon'),
                        datecreated=mark.get('datecreated'),
                        tags=taglist,
                        source=source
                    ):
                        count += 1
            return count
        except Exception as e:
            log.debug(str(e))
            return -1


class HashmarksSynchronizer:
    syncing = AsyncSignal(bool)

    async def syncTask(self):
        try:
            while True:
                await asyncio.sleep(60)

                sources = await database.hashmarkSourcesNeedSync(
                    minutes=60 * 3)
                count = len(sources)

                if count > 0:
                    log.debug(
                        'Unsynced sources: {}, syncing now'.format(count))
                    await self.sync()
        except asyncio.CancelledError:
            log.debug('Sync task cancelled')
        except Exception as err:
            log.debug(f'Sync task error: {err}')

    async def sync(self):
        _count, _scount = 0, 0

        await self.syncing.emit(True)

        log.info('Synchronizing hashmarks database ...')

        sources = await database.hashmarkSourceAll()

        for source in sources:
            if source.type == HashmarkSource.TYPE_PYMODULE:
                loader = ModuleCatalogLoader()
            # elif source.type == HashmarkSource.TYPE_GITREPOS:
            #     loader = GitCatalogLoader()
            elif source.type == HashmarkSource.TYPE_IPFSMARKS_LEGACY:
                loader = IPFSMarksCatalogLoader()
            elif source.type == HashmarkSource.TYPE_YAML_ARCHIVE:
                loader = YAMLArchiveLoader()
            else:
                continue

            log.info(f'Synchronizing: {source}')

            _count += await loader.load(source)

            if _count >= 0:
                _scount += 1
                source.syncedlast = datetime.now()
                await source.save()

        shistory = database.HashmarkSyncHistory(
            hashmarkstotal=await database.hashmarksCount(),
            hashmarksadded=_count,
            srcsynccount=_scount
        )
        await shistory.save()

        await self.syncing.emit(False)
