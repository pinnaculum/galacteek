import pytest


from galacteek import database
from galacteek.database.models import *
from galacteek.hashmarks import *
from galacteek.ipfs.cidhelpers import *
from galacteek.core import iptags


@pytest.fixture
def dbpath(tmpdir):
    return tmpdir.join('db.sqlite3')


class TestDatabase:
    @pytest.mark.parametrize(
        'path1,path2,path3,path4',
        [
            ('/ipfs/QmT1TPVjdZ9CRnqwyQ9WygDoRgRRibFrEyWufenu92SuUV',
             '/ipfs/QmT1TPVjdZ9CRnqwyQ9WygDoRgRRibFrEyWufenu92SuUV/a/abcdef',
             '/ipfs/Qma1TPVjdZ9CReqwyQ9Wvv3oRgRRi5FrEyWufenu92SuUV/www/',
             '/ipfs/Qma8TPVjdZ3CReqwyQ9Wvv3oggRRi3FrEyWufenu92SuUV/src/',
             )])
    @pytest.mark.parametrize('title', ['Broken glass'])
    @pytest.mark.asyncio
    async def test_hashmarks(self, dbpath, path1, path2, path3, path4, title):
        await database.initOrm(dbpath)

        mark = await database.hashmarkAdd(path1, title=title,
                                          category='test',
                                          tags=['#dapp'])
        assert await database.hashmarksExists(path1)

        await mark.fetch_related('source', 'category', 'parent')
        assert mark.category.name == 'test'
        assert mark.source.name == 'local'

        mark2 = await database.hashmarkAdd(
            path2, title='Tagged',
            tags=['#ok', '@Earth#dapp', '@Earth#cool'], parent=mark)
        await mark2.fetch_related('source', 'category')
        await mark2.fetch_related('parent')
        assert mark2.parent is not None
        assert mark2.parent.title == title

        mark3 = await database.hashmarkAdd(path3, title='Tagged2',
                                           objtags=['@Earth#dapp'])

        await database.hashmarkAdd(
            path4, title='Tagged2',
            objtags=['@Earth#ok', '@Earth#cool'])
        await mark3._fetch_all()

        await database.hashmarkMappingAdd('ddd', '', mark2.path)

        maps = await database.hashmarkMappingsAll()
        for map in maps:
            await map.fetch_related('qahashmark')
            print(map.name, map.qahashmark.url)

        res = await database.hashmarksByTags(['@Earth#ok'])
        assert res.pop().title == 'Tagged'
        res = await database.hashmarksByTags(['@Earth#cool'])
        assert res.pop().title == 'Tagged'
        res = await database.hashmarksByTags(['#cool'], defaultPlanet=False)
        assert res.pop().title == 'Tagged'

        res = await database.hashmarksByObjTags(['#dapp'], defaultPlanet=False)
        assert res.pop().title == 'Tagged2'

        mark3 = await database.hashmarkAdd('ens://test.eth',
                                           title='ENS', tags=['@Earth#ens'])
        assert mark3.url == 'ens://test.eth'
        assert mark3.path is None

        tags = list(reversed(await database.hashmarksPopularTags(min=1)))
        assert tags.pop().name == '@Earth#dapp'
        assert tags.pop().name == '@Earth#ok'

        await database.closeOrm()

    @pytest.mark.parametrize(
        'path1,path2,path3,path4',
        [
            ('/ipfs/QmT1TPVjdZ9CRnqwyQ9WygDoRgRRibFrEyWufenu92SuUV',
             '/ipfs/QmT1TPVjdZ9CRnqwyQ9WygDoRgRRibFrEyWufenu92SuUV/a/abcdef',
             '/ipfs/Qma1TPVjdZ9CReqwyQ9Wvv3oRgRRi5FrEyWufenu92SuUV/www/',
             '/ipfs/Qma8TPVjdZ3CReqwyQ9Wvv3oggRRi3FrEyWufenu92SuUV/src/',
             )])
    @pytest.mark.parametrize('title', ['Broken glass'])
    @pytest.mark.asyncio
    async def test_history(self, dbpath, path1, path2, path3, path4, title):
        await database.initOrm(dbpath)
        p = IPFSPath(path1, autoCidConv=True)

        item, visit = await database.urlHistoryRecord(p.ipfsUrl, title)

        await visit.fetch_related('historyitem')
        assert visit.historyitem.id == item.id
        assert visit.historyitem.url == p.ipfsUrl

        # TODO
        await database.urlHistorySearch(title)

        await database.closeOrm()

    def test_iptags(self):
        assert iptags.ipTag('test') == '@Earth#test'
        assert iptags.ipTag('test', 'Mars') == '@Mars#test'

        assert iptags.ipTagsFormat('test', defaultPlanet=False) == '#test'
        assert iptags.ipTagsFormat('#test', defaultPlanet=False) == '#test'
        assert iptags.ipTagsFormat('#test') == '@Earth#test'
        assert iptags.ipTagsFormat('@Mars#test') == '@Mars#test'


class TestCatalogLoader:
    @pytest.mark.asyncio
    async def test_modloader(self, dbpath):
        await database.initOrm(dbpath)

        await database.hashmarkSourceAdd(
            HashmarkSource.TYPE_PYMODULE,
            'galacteek.hashmarks.default',
            name='pkg1')
        res = await database.hashmarkSourceSearch(
            name='pkg1',
            type=HashmarkSource.TYPE_PYMODULE)
        assert res.name == 'pkg1'
        assert res.type == HashmarkSource.TYPE_PYMODULE

        await database.hashmarkSourceAdd(
            HashmarkSource.TYPE_GITREPOS,
            'https://github.com/galacteek/hashmarks-dwebland'
        )

        sync = HashmarksSynchronizer()
        await sync.sync()

        await sync.sync()

        await database.closeOrm()
