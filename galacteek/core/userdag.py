import asyncio
import uuid
import traceback

from datetime import datetime
from datetime import timezone

from feedgen.feed import FeedGenerator

from galacteek import AsyncSignal
from galacteek import asyncSigWait
from galacteek import ensure
from galacteek import log
from galacteek import logUser
from galacteek import partialEnsure
from galacteek import services
from galacteek.ipfs import ipfsOp
from galacteek.ipfs.paths import posixIpfsPath
from galacteek.ipfs.cidhelpers import ipnsKeyCidV1
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ipfs.cidhelpers import joinIpns
from galacteek.ipfs.cidhelpers import stripIpfs
from galacteek.core.analyzer import ResourceAnalyzer
from galacteek.core import isoformat
from galacteek.core import pkgResourcesRscFilename
from galacteek.core import utcDatetimeIso
from galacteek.core import titleToPostName
from galacteek.core.asynclib import SignalNotEmittedError
from galacteek.dweb import render
from galacteek.dweb.markdown import markitdown
from galacteek.dweb.atom import DWEB_ATOM_FEEDFN
from galacteek.dweb.atom import DWEB_ATOM_FEEDGWFN

from galacteek.ipfs.dag import EvolvingDAG
from galacteek.ld import ipsContextUri


POSTS_NODEKEY = 'posts'
BYTAG_NODEKEY = 'bytag'
METADATA_NODEKEY = '_metadata'
BLOG_NODEKEY = 'blog'
PINREQS_NODEKEY = 'pinrequests'


class UserDAG(EvolvingDAG):
    def updateDagSchema(self, root):
        changed = False

        if BLOG_NODEKEY not in root:
            root[BLOG_NODEKEY] = {
                '@type': 'DwebBlog',
                'title': {
                    'en': 'dblog'
                },
                'dateCreated': utcDatetimeIso(),

                POSTS_NODEKEY: {},
                BYTAG_NODEKEY: {}
            }
            changed = True

        if POSTS_NODEKEY not in root[BLOG_NODEKEY]:
            root[BLOG_NODEKEY][POSTS_NODEKEY] = {}
            changed = True

        if BYTAG_NODEKEY not in root[BLOG_NODEKEY]:
            root[BLOG_NODEKEY][BYTAG_NODEKEY] = {}
            changed = True

        root[BLOG_NODEKEY].update({
            '@type': 'DwebBlog',
        })

        if PINREQS_NODEKEY not in root:
            root[PINREQS_NODEKEY] = []
            changed = True

        if METADATA_NODEKEY not in root:
            root[METADATA_NODEKEY] = {
                'site_name': '',
                'site_description': '',
                'dateUpdated': utcDatetimeIso()
            }
            changed = True

        return changed

    async def initDag(self, ipfsop):
        return {
            'index.html': 'Blank',

            'media': {
                'images': {}
            }
        }

    async def siteMetadata(self):
        return await self.get(METADATA_NODEKEY)

    async def neverUpdated(self):
        metadata = await self.siteMetadata()
        if not metadata:
            return False

        return metadata.get('dateModified') is None


class UserWebsite:
    """
    The website associated to the user.

    Later on this should become more generic to create all kinds of apps
    """

    def __init__(self, edag, profile, ipnsKeyId, jinjaEnv, parent=None):
        self._profile = profile
        self._ipnsKeyId = ipnsKeyId
        self._edag = edag
        self._jinjaEnv = jinjaEnv
        self._assetsEntry = None

        self._atomFeedFn = DWEB_ATOM_FEEDFN
        self._atomFeedGwFn = DWEB_ATOM_FEEDGWFN

        self._rscAnalyzer = ResourceAnalyzer(None)
        self._updating = False

        # Signal for then user website was rebuilt from the user dag
        self.websiteUpdated = AsyncSignal()

        self.dagUser.dagDataChanged.connect(
            partialEnsure(self.onDagUserChanged))

    @property
    def edag(self):
        return self._edag

    @property
    def profile(self):
        return self._profile

    @property
    def pronto(self):
        return services.getByDotName('ld.pronto')

    @property
    def iSchemeService(self):
        return services.getByDotName('dweb.schemes.i')

    @property
    def updating(self):
        return self._updating

    @property
    def ipnsKey(self):
        return self._ipnsKeyId

    @property
    def siteUrl(self):
        return self.sitePath.ipfsUrl

    @property
    def sitePath(self):
        return IPFSPath(joinIpns(self.ipnsKey))

    @property
    def atomFeedPath(self):
        return self.sitePath.child(self._atomFeedFn)

    @property
    def rssFeedPath(self):
        return self.sitePath.child('rss.xml')

    @property
    def dagUser(self):
        return self.profile.dagUser

    @property
    def dagRoot(self):
        return self.profile.dagUser.root

    @property
    def dagRequests(self):
        return self.dagRoot['pinrequests']

    @property
    def dagBlog(self):
        return self.dagRoot[BLOG_NODEKEY]

    @property
    def dagBlogPosts(self):
        return self.dagRoot[BLOG_NODEKEY]['posts']

    @property
    def defaultTitle(self):
        return f'dblog: {self.profile.userInfo.spaceHandle.human}'

    def debug(self, msg):
        return self.profile.debug(msg)

    def blogPostsCount(self):
        if self.dagBlogPosts:
            return len(self.dagBlogPosts.keys())

        return 0

    def pathToPost(self, postName: str) -> str:
        return posixIpfsPath.join(BLOG_NODEKEY,
                                  POSTS_NODEKEY,
                                  postName)

    def pathToPostView(self, postName: str) -> str:
        return posixIpfsPath.join(self.pathToPost(postName), 'view')

    @ ipfsOp
    async def graph(self, ipfsop):
        async with ipfsop.ldOps() as ld:
            return await ld.rdfify(self.dagBlog)

    @ ipfsOp
    async def postGraph(self, ipfsop, postName: str):
        async with ipfsop.ldOps() as ld:
            return await ld.rdfify(self.dagBlogPosts[postName])

    async def blogEntries(self):
        """
        Return the list of names of blog posts in the DAG
        """

        listing = await self.edag.list(path=f'{BLOG_NODEKEY}/posts')

        return [entry for entry in listing if entry != 'index.html' and
                not entry.startswith('_') and not entry.startswith('@')]

    async def blogPostRemove(self, postName: str):
        """
        Remove the blog post from the DAG with the given postName
        """

        async with self.edag as dag:
            blogPosts = dag.root[BLOG_NODEKEY][POSTS_NODEKEY]

            if postName in blogPosts:
                del blogPosts[postName]
            else:
                raise ValueError(f'No post with name {postName}')

        return True

    async def blogPostGet(self, postName: str):
        """
        Get the blog post from the DAG with the given postName
        """
        if postName in self.dagBlogPosts:
            return self.dagBlogPosts[postName]
        else:
            raise ValueError(f'No post with name {postName}')

    async def blogPostChange(self,
                             postName: str,
                             body: str,
                             title: str,
                             langTag: str = 'en') -> bool:
        async with self.edag as dag:
            blog = dag.root[BLOG_NODEKEY][POSTS_NODEKEY]

            if postName in blog:
                post = blog[postName]

                post['body'][langTag] = body
                post['title'][langTag] = title
                post['dateModified'] = utcDatetimeIso()
            else:
                raise ValueError(f'No post with name {postName}')

        return True

    @ ipfsOp
    async def blogPost(self, ipfsop,
                       title: str,
                       msg: str,
                       category: str = None,
                       tags: list = [],
                       author=None,
                       langTag: str = 'en',
                       ldContextName='DwebBlogPost') -> IPFSPath:
        """
        Post to the blog
        """

        sHandle = self.profile.userInfo.spaceHandle
        username = sHandle.human
        uid = str(uuid.uuid4())
        postName = titleToPostName(title.strip().lower())

        async def create():
            async with self.edag:
                exEntries = await self.blogEntries()
                if not postName or postName in exEntries:
                    raise Exception(
                        'A blog post with this name already exists')

                now = datetime.now(timezone.utc)

                # Create the DAG node for this post
                # Its view will be rendered later on

                self.dagBlogPosts[postName] = {
                    '@context': ipsContextUri(ldContextName),
                    '@type': ldContextName,

                    '@id': self.iSchemeService.iriGenObject(ldContextName),

                    'didAuthor': self.profile.userInfo.personDid,
                    'didCreator': self.profile.userInfo.personDid,

                    'body': {
                        langTag: msg
                    },
                    'title': {
                        langTag: title
                    },
                    'uuid': uid,
                    'postName': postName,  # name of the post's DAG node
                    'tags': tags,
                    'author': author if author else username,
                    'datePublished': isoformat(now),
                    'dateModified': isoformat(now)
                }

        # Wait for update() to rebuild and watch out for websiteUpdated
        try:
            async with asyncSigWait(self.websiteUpdated,
                                    timeout=8.0):
                await create()
                await asyncio.sleep(5)
        except (SignalNotEmittedError, BaseException) as err:
            log.info(f'websiteUpdated signal was not fired: {err}')
            return None
        else:
            log.debug('websiteUpdated signal was fired')

        # Get the ipfs path to the post's view page
        resolved = IPFSPath(
            await self.dagUser.resolve(self.pathToPostView(postName)),
            autoCidConv=True
        )

        if resolved.isIpfsRoot and resolved.valid:
            # Register the post by tag

            async with self.edag as dag:
                byTags = dag.root[BLOG_NODEKEY][BYTAG_NODEKEY]

                for tag in tags:
                    if tag is None:
                        continue

                    tagged = byTags.setdefault(tag, {'@graph': []})
                    tagged['@graph'].append({
                        'name': postName,
                        'title': title,
                        'view': {
                            '/': stripIpfs(str(resolved))
                        }
                    })
                    byTags[tag]['index.html'] = await self.renderLink(
                        'usersite/bytag.html',
                        contained=True,
                        tag=tag,
                        tagposts=tagged['@graph'],
                        title=f'Posts with tag: {tag}'
                    )
        else:
            logUser.info('Empty blog post')
            return None

        logUser.info('Your blog post is online')
        return resolved

    @ipfsOp
    async def makePinRequest(self, op, title, descr, objects,
                             priority=0, tags=None):
        async with self.profile.dagUser as dag:
            # objects needs to be a list of IPFS objects paths

            if not isinstance(objects, list):
                return False

            username = self.profile.userInfo.spaceHandle.human
            uid = str(uuid.uuid4())
            now = utcDatetimeIso()

            objsReq = []

            for obj in objects:
                path = IPFSPath(obj)
                if not path.valid:
                    continue

                try:
                    mType, statInfo = await self._rscAnalyzer(path)
                except:
                    continue

                if not statInfo.valid:
                    continue

                objsReq.append({
                    'path': path.objPath,
                    'totalsize': statInfo.totalSize,
                    'content_type': str(mType) if mType else None
                })

            pinRequest = {
                'pinrequest': {
                    'body': None,
                    'title': title,
                    'description': descr,
                    'objects': objsReq,
                    'uuid': uid,
                    'tags': tags if tags else [],
                    'author': username,
                    'priority': priority,
                    'datePublished': isoformat(now),
                    'version': 1
                }
            }

            dag.dagRoot[PINREQS_NODEKEY].append(pinRequest)

        return True

    @ipfsOp
    async def importAssets(self, ipfsop) -> None:
        assetsPath = pkgResourcesRscFilename('galacteek.templates',
                                             'usersite/assets')
        self._assetsEntry = await ipfsop.addPath(assetsPath, recursive=True)

    @ipfsOp
    async def init(self, ipfsop):
        # Import the assets

        await self.importAssets()

        if self.profile.ctx.hasRsc('ipfs-cube-64'):
            self.edag.root['media']['images']['ipfs-cube.png'] = \
                self.edag.mkLink(self.profile.ctx.resources['ipfs-cube-64'])
        if self.profile.ctx.hasRsc('atom-feed'):
            self.edag.root['media']['images']['atom-feed.png'] = \
                self.edag.mkLink(self.profile.ctx.resources['atom-feed'])

        self.edag.root['about.html'] = await self.renderLink(
            'usersite/about.html',
            title=self.defaultTitle
        )

        if self.blogPostsCount() == 0:
            await self.blogPost('Hello',
                                'Your dblog is up',
                                langTag='en')

    def createFeed(self, ftype='ipfs'):
        # Create the feed

        sHandle = self.profile.userInfo.spaceHandle

        feed = FeedGenerator()
        feed.id(self.siteUrl)
        feed.title(f"dfeed: {sHandle.human}")
        feed.author({'name': sHandle.human})

        if ftype == 'ipfs':
            feed.link(href=self.atomFeedPath.ipfsUrl, rel='self')
        elif ftype == 'publicgw':
            feed.link(href=self.atomFeedPath.publicGwUrl, rel='self')

        feed.language('en')  # BC
        return feed

    async def updateAboutPage(self):
        async with self.profile.dagUser as dag:
            dag.root['about.html'] = await self.renderLink(
                'usersite/about.html',
                title=self.defaultTitle
            )
            dag.root['media']['images']['avatar'] = \
                self.profile.userInfo.avatar

    async def onDagUserChanged(self):
        try:
            async with self.dagUser.wLock:
                await self.update()
        except Exception:
            traceback.print_exc()

    @ipfsOp
    async def update(self, op):
        if self.dagRoot is None or self.updating is True:
            return

        dag = self.profile.dagUser

        self._updating = True

        assetsChanged = False
        blogPosts = []

        if '@id' not in self.dagBlog:
            # Gen an @id for the blog
            self.dagBlog['@id'] = self.iSchemeService.iriGenObject(
                'DwebBlog'
            )
            self.dagBlogPosts['@id'] = self.iSchemeService.iriGenObject(
                'DwebBlogPosts'
            )

        feed = self.createFeed()
        feedgw = self.createFeed(ftype='publicgw')

        if self._assetsEntry:
            resolved = await dag.resolve('assets')
            if resolved and self._assetsEntry.get('Hash') != resolved:
                # The assets were modified (will need to fully regen)
                assetsChanged = True

            dag.root['assets'] = dag.mkLink(self._assetsEntry)

        # Graph
        siteGraph = await self.graph()
        if siteGraph:
            blogs = self.pronto.graphByUri(
                'urn:ipg:i:love:blogs'
            )

            if blogs:
                await blogs.guardian.mergeReplace(siteGraph, blogs)

        bEntries = await self.blogEntries()

        for entry in bEntries:
            await op.sleep()

            if entry == BYTAG_NODEKEY or entry not in self.dagBlogPosts:
                continue

            # nList = await dag.list(path=f'{BLOG_NODEKEY}/{entry}')
            nList = await dag.list(path=f'{BLOG_NODEKEY}/posts/{entry}')

            post = await dag.get(
                f'{BLOG_NODEKEY}/{POSTS_NODEKEY}/{entry}'
            )

            # Don't use anything that's not typed
            if not isinstance(post, dict) or '@type' not in post:
                continue

            blogPosts.append(post)

            if 'view' in nList and assetsChanged is False:
                continue

            self.dagBlogPosts[entry]['view'] = await self.renderLink(
                'usersite/blog_post.html',
                contained=True,
                post=post,
                title=post['title']['en']
            )

        def postOrder(post: dict):
            try:
                if 'datePublished' in post:
                    return post['datePublished']
                elif 'date_published' in post:
                    # Old field name
                    return post['date_published']
            except Exception:
                return None

        blogPosts = sorted(blogPosts,
                           key=postOrder,
                           reverse=True)

        self.feedAddPosts(blogPosts, feed)
        self.feedAddPosts(blogPosts, feedgw, ftype='publicgw')

        dag.root['index.html'] = await self.renderLink(
            'usersite/home.html',
            blogUri=self.dagBlog['@id']
        )

        self.dagBlog['index.html'] = await self.renderLink(
            'usersite/blog.html',
            posts=blogPosts,
            siteGraph=siteGraph,
            siteGraphTtl=(await siteGraph.ttlize()).decode(),
            title=self.defaultTitle
        )

        dag.root['about.html'] = await self.renderLink(
            'usersite/about.html',
            title=self.defaultTitle
        )

        # Finally, generate the Atom feed and put it in the graph
        try:
            atomFeed = feed.atom_str(pretty=True)
            entry = await op.addBytes(atomFeed)
            atomFeedGw = feedgw.atom_str(pretty=True)
            entryGw = await op.addBytes(atomFeedGw)

            if entry:
                # Unpin the old feed (disabled for now)
                if self._atomFeedFn in dag.root and 0:
                    resolved = await dag.resolve(
                        path=self._atomFeedFn)
                    if resolved:
                        ensure(op.unpin(resolved))

                dag.root[self._atomFeedFn] = dag.mkLink(entry)

            if entryGw:
                dag.root[self._atomFeedGwFn] = dag.mkLink(entryGw)
        except Exception as err:
            log.debug('Error generating Atom feed: {}'.format(
                str(err)))

        metadata = await dag.siteMetadata()
        metadata['dateModified'] = utcDatetimeIso()
        dag.root[METADATA_NODEKEY] = metadata

        await dag.ipfsSave(emitDataChanged=False)

        await self.websiteUpdated.emit()

        self._updating = False

    def feedAddPinRequests(self, requests, feed):
        for id, reqobj in enumerate(requests):
            req = reqobj['pinrequest']
            rpath = self.sitePath.child(posixIpfsPath.join(
                PINREQS_NODEKEY, str(id), 'view'))

            fEntry = feed.add_entry()
            fEntry.title('Pin request: {}'.format(req['title']))
            fEntry.id(rpath.ipfsUrl)
            fEntry.link(href=rpath.ipfsUrl, rel='alternate')
            fEntry.published(req['datePublished'])
            fEntry.author({'name': self.profile.userInfo.iphandle})

    def feedAddPosts(self, blogPosts, feed, ftype='ipfs'):
        for post in blogPosts:
            ppath = self.sitePath.child(self.pathToPostView(post['postName']))

            fEntry = feed.add_entry()
            fEntry.title(post['title']['en'])  # BC

            if ftype == 'ipfs':
                url = ppath.ipfsUrl
            elif ftype == 'publicgw':
                url = ppath.publicGwUrl

            fEntry.id(url)
            fEntry.link(href=url, rel='alternate')
            fEntry.updated(post['dateModified'])
            fEntry.published(post['datePublished'])
            fEntry.content(
                content=markitdown(post['body']['en']),  # BC: hard-coded lang
                type='html'
            )

            fEntry.author({'name': self.profile.userInfo.iphandle})

            for tag in post['tags']:
                fEntry.category(term=tag)

    async def tmplRender(self, tmpl, contained=False, **kw):
        coro = render.ipfsRender if not contained else \
            render.ipfsRenderContained

        ipnsKeyV1 = ipnsKeyCidV1(self.ipnsKey)

        return await coro(self._jinjaEnv,
                          tmpl,
                          profile=self.profile,
                          dag=self.edag.dagRoot,
                          siteIpns=ipnsKeyV1,
                          atomFeedrUrl=self.atomFeedPath.ipfsUrl,
                          **kw)

    async def renderLink(self, tmpl, contained=False, **kw):
        # Render and link in the dag

        result = await self.tmplRender(tmpl, contained=contained, **kw)

        if result:
            return self.edag.mkLink(result)
        else:
            raise Exception(f'Could not render {tmpl} with args {kw}')
