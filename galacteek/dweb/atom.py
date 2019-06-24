import json
import feedparser
from dateutil import parser

import aioipfs

from PyQt5.QtCore import QObject
from PyQt5.QtCore import pyqtSignal

from galacteek import log
from galacteek.ipfs import ipfsOp
from galacteek.ipfs.cidhelpers import IPFSPath


DWEB_ATOM_FEEDFN = 'dfeed.atom'


class AtomFeedExistsError(Exception):
    pass


class AtomFeedError(Exception):
    pass


class AtomParseFeedError(Exception):
    pass


def parseFeed(data):
    try:
        feed = feedparser.parse(data)
    except:
        log.debug('Feed parsing error')
        return None
    else:
        return feed


class IPFSAtomFeedEntry(QObject):
    statusChanged = pyqtSignal(int)

    ENTRY_STATUS_NEW = 0
    ENTRY_STATUS_READ = 1

    def __init__(self, feed, entry, status=0):
        super().__init__()
        self._feed = feed
        self._entry = entry
        self._status = status

        self.srow_id = None

    @property
    def feed(self):
        return self._entry

    @property
    def entry(self):
        return self._entry

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, v):
        if isinstance(v, int):
            self._status = v
            self.statusChanged.emit(v)

    @property
    def id(self):
        return self.entry['id']

    @property
    def link(self):
        return self.entry['link']

    @property
    def title(self):
        return self.entry['title']

    @property
    def author(self):
        return self.entry['author']

    @property
    def updatedString(self):
        return self.entry['updated']

    @property
    def updated(self):
        return parser.parse(self.updatedString)

    @property
    def publishedString(self):
        return self.entry['published']

    @property
    def published(self):
        return parser.parse(self.publishedString)

    @property
    def tags(self):
        return [t['term'] for t in self.entry['tags']]

    def markAsRead(self):
        self.status = self.ENTRY_STATUS_READ


class IPFSAtomFeed(QObject):
    """
    An Atom feed from the dweb
    """

    statusForEntryChanged = pyqtSignal(IPFSAtomFeedEntry)

    def __init__(self, feed):
        super().__init__()
        self._feed = feed
        self._entries = []
        self._init()

    def _init(self):
        if 'entries' in self.feed:
            self._entries = [
                IPFSAtomFeedEntry(self, entry) for entry in
                self.feed['entries']
            ]

    @property
    def feed(self):
        return self._feed

    @property
    def feedDump(self):
        return json.dumps(self.feed, indent=4)

    @property
    def feedInfos(self):
        return self.feed['feed']

    @property
    def entries(self):
        return self._entries

    @property
    def title(self):
        return self.feedInfos['title']

    @property
    def language(self):
        return self.feedInfos['language']

    @property
    def id(self):
        return self.feedInfos['id']

    @property
    def author(self):
        return self.feedInfos['author']

    @property
    def generator(self):
        return self.feedInfos['generator']

    @property
    def updatedString(self):
        return self.feedInfos['updated']

    @property
    def updated(self):
        dateString = self.updatedString
        dt = parser.parse(dateString)
        return dt

    async def read(self):
        for entry in self.entries:
            yield IPFSAtomFeedEntry(entry)


class IPFSAtomFeedParser:
    @ipfsOp
    async def parse(self, ipfsop, path):
        """
        The caller already knows this object contains a feed (no MIME
        detection here)

        path can be an IPFSPath or a string

            dweb:/ipns/blog.ipfs.io/feed.atom
            dweb:/ipns/QmWmtbVRezi6AtFC8BPL1SoPFDT5jobbFpggpAb7xZTAmB/f.atom

        :param str path: feed's object path
        """

        if isinstance(path, IPFSPath):
            objPath = path.objPath
        elif isinstance(path, str):
            objPath = path
        else:
            log.debug('Unknown obj type to parse: {0}'.format(path))
            return

        try:
            data = await ipfsop.waitFor(
                ipfsop.client.cat(objPath), 10
            )

            if not data:
                return None

            feed = parseFeed(data.decode())
            if feed:
                return IPFSAtomFeed(feed=feed)
            else:
                raise AtomParseFeedError()
        except aioipfs.APIError:
            raise AtomParseFeedError()
        except Exception:
            raise AtomParseFeedError()
