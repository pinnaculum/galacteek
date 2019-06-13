import feedparser

import aioipfs

from galacteek import log
from galacteek.ipfs import ipfsOp


DWEB_ATOM_FEEDFN = 'dfeed.atom'


def parseFeed(data):
    try:
        feed = feedparser.parse(data)
    except:
        log.debug('Feed parsing error')
        return None
    else:
        return feed


class IPFSAtomFeed:
    """
    An Atom feed from the dweb
    """
    def __init__(self, feed=None):
        self._feed = feed

    @property
    def feed(self):
        return self._feed

    @feed.setter
    def feed(self, f):
        log.debug('Feed was set!')
        self._feed = f

    @ipfsOp
    async def parse(self, ipfsop, path):
        """
        The caller already knows this object contains a feed (no MIME
        detection here)

        :param str path: feed's object path
        """

        try:
            data = await ipfsop.waitFor(
                ipfsop.client.cat(path), 10
            )

            if not data:
                return None

            feed = parseFeed(data.decode())
            if feed:
                self.feed = feed
        except aioipfs.APIError:
            return None
