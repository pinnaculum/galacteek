import pytest

from galacteek.ipfs.search import multiSearch


class TestMultiSearch:
    @pytest.mark.asyncio
    async def test_multisearch(self, event_loop, localipfsop):
        async for pageCount, result in multiSearch('cyber academy'):
            assert pageCount > 100
            assert 'hit' in result
            assert result['engine'] in ['ipfs-search', 'cyber']
            assert result['hit']['hash'] is not None
            assert result['hit']['title'] is not None
