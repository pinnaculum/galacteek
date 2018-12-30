import asyncio
import time

from galacteek import log
from galacteek.core.ipfsmarks import *  # noqa
from galacteek.ipfs.ipfsops import *  # noqa
from galacteek.ipfs.wrappers import ipfsOp
from galacteek.ipfs import crawl


class FeedFollower(object):
    """
    Follows an IPNS hash reference, in the sense that it will periodically
    resolve the hash and register the resulting object path if it's new,
    adding it as a mark inside the feed object
    """

    def __init__(self, app, marks):
        self.marks = marks
        self.app = app

    @ipfsOp
    async def process(self, op):
        while True:
            feeds = self.marks.getFeeds()

            for ipnsp, feed in feeds:
                now = int(time.time())

                resolvedLast = feed.get('resolvedlast', None)
                resolveEvery = feed.get('resolveevery', 3600)
                autoPin = feed.get('autopin', False)
                feedMarks = self.marks.getFeedMarks(ipnsp)

                if resolvedLast and resolvedLast > (now - resolveEvery):
                    log.debug('{0} was resolved recently'.format(ipnsp))
                    continue

                resolved = await op.resolve(ipnsp, timeout=15, recursive=True)
                if not resolved:
                    log.debug('Could not resolve {0}'.format(ipnsp))
                    continue

                resolvedPath = resolved.get('Path', None)
                if not resolvedPath:
                    log.debug(
                        'Could not resolve {0}: invalid path'.format(ipnsp))
                    continue

                feed['resolvedlast'] = now

                if resolvedPath in feedMarks.keys():
                    # already registered
                    log.debug('Not registering {0}'.format(resolvedPath))
                    continue

                # Register the mark
                objStats = {}
                stat = await op.objStat(resolvedPath, timeout=10)
                if stat:
                    objStats = stat

                title = await crawl.getTitle(op.client, resolvedPath)

                mark = IPFSHashMark.make(
                    resolvedPath, title=title,
                    datasize=objStats.get('DataSize', None),
                    cumulativesize=objStats.get('CumulativeSize', None),
                    numlinks=objStats.get('NumLinks', None),
                    share=feed.get('share', False)
                )

                self.marks.feedAddMark(ipnsp, mark)

                if autoPin:
                    log.debug('Feed follower, autopinning {}'.format(
                        resolvedPath))
                    await self.app.ipfsCtx.pinner.queue(resolvedPath,
                                                        True, None)

            await asyncio.sleep(120)
