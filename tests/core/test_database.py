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

        await database.closeOrm()


class TestBitMessageAccounts:
    @pytest.mark.parametrize('label', ['mybm'])
    @pytest.mark.parametrize('label2', ['ole'])
    @pytest.mark.parametrize(
        'bmaddr', ['BM-87eLyoLh91n8r65S7itLzU9b3BV1y6v6d2N'])
    @pytest.mark.parametrize(
        'bmaddr2', ['BM-87eLyoLh91n8r6517vtLzU7b3BV1y6v6d2N'])
    @pytest.mark.asyncio
    async def test_create_bmaccounts(self, label, bmaddr, bmaddr2, label2):
        await database.initOrm(dbpath)

        mbox = await database.bmMailBoxRegister(
            bmaddr,
            label,
            bmaddr,
            default=True
        )
        assert mbox is not None
        assert mbox.prefs is not None
        assert mbox.prefs.cContentType == 'text/plain'
        assert mbox.prefs.markupType == 'markdown'
        assert mbox.mDirType == 0

        # Fail to create a mailbox with same address
        mbox = await database.bmMailBoxRegister(
            bmaddr,
            'otherlabel',
            bmaddr
        )
        assert mbox is None

        # Fail to create a mailbox with same label
        mbox = await database.bmMailBoxRegister(
            bmaddr2,
            label,
            bmaddr
        )
        assert mbox is None

        # Create second account
        mbox2 = await database.bmMailBoxRegister(
            bmaddr2,
            label2,
            bmaddr2
        )
        assert mbox2 is not None
        assert mbox2.bmAddress == bmaddr2

        mbox = await database.bmMailBoxGet(bmaddr)
        assert mbox.bmAddress == bmaddr
        assert mbox.label == label
        assert mbox is not None

        # Check the default get
        mbox = await database.bmMailBoxGetDefault()
        assert mbox is not None
        assert mbox.bmAddress == bmaddr

        assert await database.bmMailBoxSetDefault(bmaddr2) is True
        mbox = await database.bmMailBoxGetDefault()
        assert mbox is not None
        assert mbox.bmAddress == bmaddr2

        await database.closeOrm()

    @pytest.mark.parametrize(
        'bmcontact1', [
            ('BM-87eLyoLh91n8r65S7itLzU9b3BV1y6v6d2N', 'John Stoner')])
    @pytest.mark.parametrize(
        'bmcontact2', [
            ('BM-89eLyBLh91n8r65S7itLzU9b3BV1y6v6d2N', 'Hilary Stone')])
    @pytest.mark.parametrize(
        'bmcontact3', [
            ('BM-19eLyBLh91n8r65S7itLzU9b3BV1y6v6d2F', 'galacteek', '@')])
    @pytest.mark.asyncio
    async def test_contacts(self, bmcontact1, bmcontact2, bmcontact3):
        await database.initOrm(dbpath)

        contact = await database.bmContactAdd(
            'invalidaddr',
            'some name'
        )
        assert contact is None

        contact = await database.bmContactAdd(
            bmcontact1[0],
            bmcontact1[1]
        )
        assert contact is not None
        assert contact.fullname == bmcontact1[1]

        contact = await database.bmContactAdd(
            bmcontact2[0],
            bmcontact2[1]
        )

        contact = await database.bmContactAdd(
            bmcontact3[0],
            bmcontact3[1],
            separator=bmcontact3[2]
        )
        assert contact is not None
        assert contact.cSeparator == '@'

        assert await database.bmMailBoxCount() == 2

        contacts = await database.bmContactByName(bmcontact1[1])
        assert len(contacts) == 1
        assert contacts.pop().fullname == bmcontact1[1]

        contacts = await database.bmContactByName('stone')
        assert len(contacts) == 2

        contact = await database.bmContactByNameFirst(
            bmcontact3[1],
            separator=bmcontact3[2]
        )
        assert contact.fullname == bmcontact3[1]

        await database.closeOrm()
