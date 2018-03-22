import pytest

from galacteek.core.marks import *

@pytest.fixture
def bmarks():
    return Bookmarks()

class TestBookmarks:
    @pytest.mark.parametrize('hash',
        ['/ipfs/QmT1TPVjdZ9CRnqwyQ9WygDoRgRRibFrEyWufenu92SuUV'])
    @pytest.mark.parametrize('title', ['My sincere apologies'])
    def test_simpleadd(self, bmarks, hash, title):
        bmarks.empty('main')
        assert bmarks.add(hash, title=title) == True
        assert bmarks.add(hash, title=title) == False
        bmarks.dump()

        assert bmarks.search(url=hash)['title'] == title
        assert bmarks.search(url=hash, category='random') == None
