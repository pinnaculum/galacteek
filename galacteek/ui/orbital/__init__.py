from PyQt5.QtCore import QObject, pyqtSlot, pyqtSignal, QJsonValue
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import QWebEngineView

from datetime import datetime

from galacteek import ensure
from galacteek.core import isoformat
from galacteek.ipfs.wrappers import ipfsOp
from galacteek.ipfs.cidhelpers import cidValid
from galacteek.ipfs.cidhelpers import joinIpfs
from galacteek.dweb import render


class FeedHandler(QObject):
    newMessages = pyqtSignal(int)
    ready = pyqtSignal(list)
    postingAllowed = pyqtSignal(bool)

    def __init__(self, connector, database, parent):
        super().__init__(parent)
        self.posts = []
        self.connector = connector
        self.database = database
        self.connector.registerEventListener(self.onEvent)
        self.destroyed.connect(self.onDestroyed)
        ensure(self.isUserRegistered())

    def onDestroyed(self, obj):
        pass

    async def onEvent(self, event):
        if event['type'] == 'replicate-progress':
            pass
        elif event['type'] == 'replicated':
            self.newMessages.emit(0)

    @pyqtSlot()
    def reload(self):
        ensure(self.loadPosts())

    @pyqtSlot()
    def getPosts(self):
        return self.posts

    @ipfsOp
    async def isUserRegistered(self, ipfsop):
        usernames = await self.connector.usernamesList()
        profile = ipfsop.ctx.currentProfile
        allowed = profile.userInfo.usernameSet and \
            profile.userInfo.username in usernames
        self.postingAllowed.emit(allowed)

    @ipfsOp
    async def loadPosts(self, ipfsop):
        posts = await self.database.list(limit=10, reverse=False)
        formatted = []

        for rawpost in posts:
            if 'value' not in rawpost:
                continue
            post = rawpost['value']
            formatted.append({
                'hash': rawpost['hash'],
                'author': post.get('author', 'Unknown'),
                'date': post.get('date', ''),
                'links': post.get('links', []),
                'message': post.get('post', ''),
            })

        self.ready.emit(formatted)
        self.posts = posts

    @pyqtSlot(QJsonValue)
    def postMessage(self, msg):
        message = msg.toString()
        ensure(self.post(message))

    @ipfsOp
    async def post(self, op, message):
        profile = op.ctx.currentProfile
        username = profile.userInfo.username

        links = []
        words = message.split()
        for word in words:
            if cidValid(word):
                links.append(joinIpfs(word))

        await self.database.add(
            {
                'author': username,
                'post': message,
                'links': links,
                'date': isoformat(datetime.now(), timespec='seconds')
            })
        self.newMessages.emit(0)


class OrbitFeedView(QWebEngineView):
    def __init__(self, connector, database, parent=None):
        super().__init__(parent)
        self.connector = connector
        self.database = database
        self.channel = QWebChannel()
        self.handler = FeedHandler(connector, self.database, self)
        self.channel.registerObject('orbitalfeed', self.handler)
        self.page().setWebChannel(self.channel)

        self.destroyed.connect(self.onDestroyed)
        ensure(self.load())

    def onDestroyed(self, obj):
        pass

    async def load(self):

        env = render.defaultJinjaEnv()
        tmpl = env.get_template('orbital/feed.html')

        if 0:
            posts = await self.connector.list('default', 'news', limit=5)
            formatted = []
            for post in posts:
                post = post['payload']['value']
                formatted.append({
                    'author': post.get('author', 'Unknown'),
                    'date': post.get('date', ''),
                    'message': post.get('post', ''),
                })

        rendered = tmpl.render(posts=[])
        self.page().setHtml(rendered)

    def onClose(self):
        return True
