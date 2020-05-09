import asyncio
from datetime import datetime
from datetime import timedelta

from galacteek import log
from galacteek import database

from galacteek.ipfs import crawl
from galacteek.ipfs.ipfsops import *  # noqa
from galacteek.ipfs.wrappers import ipfsOp
from galacteek.ipfs.cidhelpers import IPFSPath


class FeedFollower(object):
    """
    IPNS object follower
    """

    def __init__(self, app):
        self.app = app

    async def process(self):
        try:
            await self.processIpnsFeeds()
        except asyncio.CancelledError:
            pass
        except asyncio.TimeoutError:
            pass
        except BaseException as err:
            log.debug('IPNS follower: unknown error ocurred: {}'.format(
                str(err)))

    @ipfsOp
    async def processIpnsFeeds(self, op):
        while True:
            now = datetime.now()

            feeds = await database.ipnsFeedsNeedSync(minutes=2)

            for feed in feeds:
                await feed.fetch_related('feedhashmark')

                autoPin = feed.autopin

                feedMarks = await feed.entries()

                resolved = await op.nameResolveStreamFirst(
                    feed.feedhashmark.path,
                    timeout=15
                )

                if not resolved:
                    log.debug('Could not resolve {0}'.format(
                        feed.feedhashmark.path))
                    continue

                resolvedPathRaw = resolved.get('Path', None)
                if not resolvedPathRaw:
                    log.debug(
                        'Could not resolve {0}: invalid path'.format(ipnsp))
                    continue

                resolvedPath = IPFSPath(resolvedPathRaw, autoCidConv=True)
                if not resolvedPath.valid:
                    continue

                feed.resolvedlast = now
                feed.resolvenext = now + timedelta(seconds=feed.resolveevery)
                await feed.save()

                exists = False
                for mark in feedMarks:
                    if mark.path == str(resolvedPath):
                        # already registered
                        exists = True
                        break

                if exists:
                    continue

                # Register the hashmark
                title = await crawl.getTitle(op.client, str(resolvedPath))

                mark = await database.hashmarkAdd(
                    resolvedPath.objPath, title=title,
                    parent=feed.feedhashmark
                )

                await database.IPNSFeedMarkAdded.emit(feed, mark)

                if autoPin:
                    log.debug('Feed follower, autopinning {}'.format(
                        resolvedPath))
                    await self.app.ipfsCtx.pinner.queue(resolvedPath.objPath,
                                                        True, None)

            await asyncio.sleep(60)
