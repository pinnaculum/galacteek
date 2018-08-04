import pytest

from galacteek.core.ipfsmarks import *

@pytest.fixture
def bmarks(tmpdir):
    return IPFSMarks(str(tmpdir.join('bm')))

@pytest.fixture
def bmarks2(tmpdir):
    return IPFSMarks(str(tmpdir.join('bm2')))

class TestMarks:
    @pytest.mark.parametrize('path1,path2,path3', [
        (
            '/ipfs/QmT1TPVjdZ9CRnqwyQ9WygDoRgRRibFrEyWufenu92SuUV/',
            '/ipfs/QmT1TPVjdZ9CRnqwyQ9WygDoRgRRibFrEyWufenu92SuUV/a/abcdefgh/system/ak/',
            '/ipfs/Qma1TPVjdZ9CReqwyQ9Wvv3oRgRRi5FrEyWufenu92SuUV/www'
        )])
    @pytest.mark.parametrize('title', ['Broken glass'])
    def test_simpleadd(self, bmarks, path1, path2, path3, title):
        assert bmarks.add(path1, title=title, tags=['dev']) == True
        assert bmarks.add(path1, title=title) == False
        assert bmarks.add(path2, title=title) == True

        marks = bmarks.getCategoryMarks('general')
        for path, mark in marks.items():
            assert mark['metadata']['title'] == title

        assert bmarks.add(path3, title='Random', category='no/way') == True

        def deleted(m):
            mDeleted = m

        bmarks.markDeleted.connect(deleted)

        assert bmarks.delete(path2) != None
        assert bmarks.search(path2) == None

        assert bmarks.search(path1, tags=['not']) == None
        assert bmarks.search(path1, tags=['dev']) != None

        assert bmarks.add(path2, title=title) == True

        path, mark = bmarks.search(path1)
        assert mark['metadata']['title'] == title

        c = bmarks.addCategory('tests', parent=None)
        cats = bmarks.getCategories()
        assert 'general' in cats
        assert 'tests' in cats
        assert 'no/way' in cats

        bmarks.dump()

    @pytest.mark.parametrize('path',
            ['/ipfs/QmT1TPVjdZ9CRnqwyQ9WygDoRgRRibFrEyWufenu92SuUV/'])
    def test_fromjson(self, bmarks, path):
        m = IPFSHashMark.make(path, title='One')
        mark = IPFSHashMark.fromJson(m.data)

    @pytest.mark.parametrize('path1,path2,path3', [
        (
            '/ipfs/QmT1TPVjdZ9CRnqwyQ9WygDoRgRRibFrEyWufenu92SuUV/',
            '/ipfs/QmT1TPVjdZ9CRnqwyQ9WygDoRgRRibFrEyWufenu92SuUV/a/abcdefgh/system/ak/',
            '/ipfs/Qma1TPVjdZ9CReqwyQ9Wvv3oRgRRi5FrEyWufenu92SuUV/www'
        )])
    @pytest.mark.parametrize('title', ['Smooth ride'])
    def test_merge(self, bmarks, bmarks2, path1, path2, path3, title):
        bmarks.add(path1, title=title, tags=['dev'])
        bmarks2.add(path2, category='www/sub/cat', title=title)
        bmarks2.add(path3, category='www/other', title=title)
        bmarks.merge(bmarks2)

        assert bmarks.search(path2) != None
        assert bmarks.search(path3) != None

        bmarks2.add(path3, category='www/other', title=title)
        bmarks.dump()

    @pytest.mark.parametrize('feed1,mark1', [
            (
                '/ipns/QmT1TPVjdZ9CvngwyQ9WygDoRgRRibFrEyWufenu92SuUV',
                '/ipfs/QmT1TPVjdZ9CvngwyQ9WygDoRgRRibFrEyWufenu92SuUb',
                )])
    def test_follow(self, bmarks, feed1, mark1):
        fo = bmarks.follow(feed1, 'test', resolveevery=60)
        bmarks.feedAddMark(feed1, IPFSHashMark.make(mark1, title='ok'))
        assert bmarks.feedAddMark(feed1, IPFSHashMark.make(mark1, title='ok2')) == False
        bmarks.dump()

    @pytest.mark.parametrize('path1,path2', [
        (
            '/ipfs/QmT1TPVjdZ9CRnqwyQ9WygDoRgRRibFrEyWufenu92SuUV',
            '/ipfs/Qma1TPVjdZ9CReqwyQ9Wvv3oRgRRi5FrEyWufenu92SuUV/www'
        )])
    @pytest.mark.parametrize('title', ['Broken glass'])
    @pytest.mark.asyncio
    async def test_asyncquery(self, event_loop, bmarks, path1, path2, title):
        mark = IPFSHashMark.make(path1, title=title)
        mark.addTags(['one', 'two', 'three'])
        bmarks.walk(['one', 'two', 'three'])

        for i in range(0, 16):
            await bmarks.asyncQ.add('/ipfs/' + str(i),
                    category=str(i), title=title, tags=['dev'])
