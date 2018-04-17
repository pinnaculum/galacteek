
import sys

import aioipfs
import asyncio
import time

from galacteek.core.ipfsmarks import *
from galacteek.ipfs.ipfsops import *

class FeedFollower(object):
    """
    Follows an IPNS hash reference, in the sense that it will periodically
    resolve the hash and register the resulting object path if it's new,
    adding it as a mark inside the feed object
    """
    def __init__(self, marks):
        self.marks = marks

    async def process(self, op):
        while True:
            await asyncio.sleep(30)

            feeds = self.marks.getFeeds()
            for ipnsp, feed in feeds.items():
                now = int(time.time())

                resolvedLast = feed.get('resolvedlast', None)
                resolveEvery = feed.get('resolveevery', 3600)
                feedMarks = self.marks.getFeedMarks(ipnsp)

                if resolvedLast and resolvedLast > (now - resolveEvery):
                    continue

                resolved = await op.resolve(ipnsp)
                if not resolved:
                    continue

                resolvedPath = resolved.get('Path', None)
                if not resolvedPath:
                    continue

                feed['resolvedlast'] = now

                if resolvedPath in feedMarks.keys():
                    # already registered
                    continue

                # Register the mark
                objStats = await op.client.object.stat(resolvedPath)
                mark = IPFSMarkData.make(resolvedPath,
                        datasize=objStats.get('DataSize', None),
                        cumulativesize=objStats.get('CumulativeSize', None),
                        numlinks=objStats.get('NumLinks', None),
                        share=feed['share'])
                self.marks.feedAddMark(ipnsp, mark)
