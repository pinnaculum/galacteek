import functools
import traceback

from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QDialogButtonBox
from PyQt5.QtWidgets import QMenu
from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QSpacerItem
from PyQt5.QtWidgets import QSizePolicy

from PyQt5.QtCore import QRegExp
from PyQt5.QtCore import QObject
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import Qt

from PyQt5.QtGui import QRegExpValidator

from galacteek import ensure
from galacteek import partialEnsure
from galacteek.ipfs import ipfsOp

from .dialogs.hashmarks import IPTagsSelectDialog

from .helpers import areYouSureAsync
from .helpers import runDialogAsync
from .helpers import getMimeIcon
from .helpers import getIcon
from .helpers import messageBox
from .helpers import messageBoxAsync
from .helpers import questionBoxAsync

from .widgets import MarkdownInputWidget
from .widgets import GalacteekTab
from .widgets import PopupToolButton

from .i18n import iNewBlogPost
from .i18n import iEditObject
from .i18n import iRemove


class UserWebsiteManager(QObject):
    postError = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.newBlogPostAction = QAction(
            getMimeIcon('text/html'),
            iNewBlogPost(), self,
            triggered=self.onNewPost
        )

        self.blogMenu = QMenu('Blog')
        self.blogMenu.setIcon(getIcon('feather-pen.png'))
        self.blogMenu.addAction(self.newBlogPostAction)

    def onNewPost(self):
        pass


class WebsiteAddPostTab(GalacteekTab):
    def __init__(self, gWindow):
        super().__init__(gWindow)

        self.app = QApplication.instance()

        self.posting = 0
        self.__postEditing = None

        buttonBox = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)

        self.title = QLineEdit()
        self.title.setMaximumWidth(600)
        self.title.setAlignment(Qt.AlignCenter)
        self.title.textEdited.connect(self.onTitleEdited)

        self.postsMgr = PopupToolButton(parent=self)
        self.postsMgr.setIcon(getIcon('feather-pen.png'))
        self.postsMgr.setObjectName('blogPostsMgrButton')

        regexp = QRegExp(r"[\w_-\s.,:;\"'?]+")
        self.title.setValidator(QRegExpValidator(regexp))
        self.title.setMaxLength(128)

        titleLayout = QHBoxLayout()
        titleLayout.setSpacing(64)
        titleLayout.addWidget(self.postsMgr)
        titleLayout.addItem(
            QSpacerItem(100, 10, QSizePolicy.Minimum, QSizePolicy.Minimum))
        titleLayout.addWidget(QLabel('Title'))
        titleLayout.addWidget(self.title)
        titleLayout.addItem(
            QSpacerItem(10, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.markdownInput = MarkdownInputWidget()

        self.vLayout.setContentsMargins(20, 20, 20, 20)
        self.vLayout.addLayout(titleLayout)

        self.vLayout.addWidget(self.markdownInput)
        self.vLayout.addWidget(buttonBox, 0, Qt.AlignCenter)

        buttonBox.accepted.connect(partialEnsure(self.process))
        buttonBox.rejected.connect(partialEnsure(self.postCancelled))

        self.destroyed.connect(functools.partial(self.onDestroyed))

        ensure(self.loadPosts(hookSignals=True))

        self.title.setFocus(Qt.OtherFocusReason)

    @property
    def postEditing(self):
        return self.__postEditing

    @property
    def profile(self):
        return self.app.ipfsCtx.currentProfile

    def onDestroyed(self):
        profile = self.app.ipfsCtx.currentProfile
        profile.userWebsite.websiteUpdated.disconnect(self.onWebsiteUpdated)

    def showEvent(self, event):
        self.title.setFocus(Qt.OtherFocusReason)

    def onTitleEdited(self, text):
        self.setTabName(text if text else iNewBlogPost())

    async def onWebsiteUpdated(self):
        await self.loadPosts()

    @ipfsOp
    async def loadPosts(self, ipfsop, hookSignals=False):
        profile = ipfsop.ctx.currentProfile

        if hookSignals:
            profile.userWebsite.websiteUpdated.connectTo(self.onWebsiteUpdated)

        entries = await profile.userWebsite.blogEntries()

        self.postsMgr.menu.clear()

        for name in entries:
            menu = QMenu(name, parent=self)

            menu.addAction(iEditObject(), partialEnsure(self.onEditPost, name))
            menu.addSeparator()
            menu.addAction(
                getIcon('clear-all.png'),
                iRemove(),
                partialEnsure(self.onRemovePost, name)
            )

            self.postsMgr.menu.addMenu(menu)

        if not self.title.text() and not self.title.hasFocus():
            self.title.setFocus(Qt.OtherFocusReason)

    @ipfsOp
    async def onEditPost(self, ipfsop,
                         postName: str, *args):
        profile = ipfsop.ctx.currentProfile
        try:
            post = await profile.userWebsite.blogPostGet(postName)
            if post:
                self.__postEditing = post
                self.title.setText(post['title']['en'])
                self.markdownInput.setMarkdownText(post['body']['en'])
            else:
                raise ValueError(f'post {postName} does not exist')
        except ValueError as verr:
            await messageBoxAsync(verr)
        except Exception as err:
            await messageBoxAsync(err)

    @ipfsOp
    async def onRemovePost(self, ipfsop,
                           postName: str, *args):
        profile = ipfsop.ctx.currentProfile

        if not await areYouSureAsync():
            return False

        try:
            await profile.userWebsite.blogPostRemove(postName)
        except Exception:
            await messageBoxAsync(traceback.format_exc())
        else:
            await self.loadPosts()

    @ipfsOp
    async def process(self, ipfsop, *args):
        profile = ipfsop.ctx.currentProfile
        contents = self.markdownInput.markdownText()
        title = self.title.text()

        if len(title) == 0 or len(contents) == 0:
            return messageBox('Please provide a title and post body')

        if self.postEditing:
            # Editing an existing post

            try:
                self.posting = 1
                self.setEnabled(False)
                await profile.userWebsite.blogPostChange(
                    self.postEditing['postName'],
                    contents,
                    title
                )
            except Exception:
                await messageBoxAsync(traceback.format_exc())
            else:
                self.posting = 0
                self.tabRemove()
                return

        self.setEnabled(False)

        tagsDialog = await runDialogAsync(IPTagsSelectDialog)

        try:
            postIpfsPath = await self.blogPost(
                title, contents,
                tagsDialog.selectedTagsList
            )
        except Exception:
            await messageBoxAsync(traceback.format_exc())
        else:
            if postIpfsPath:
                await self.app.resourceOpener.open(postIpfsPath)

    @ipfsOp
    async def blogPost(self, ipfsop, title, body, tags):
        profile = ipfsop.ctx.currentProfile

        try:
            self.posting = 1
            pPath = await profile.userWebsite.blogPost(
                title, body, tags=tags)
        except Exception as err:
            self.posting = 0
            messageBox(err)
            self.setEnabled(True)
        else:
            self.posting = 2
            self.tabRemove()
            return pPath

    async def onClose(self):
        contents = self.markdownInput.markdownText()

        if self.posting == 1:
            return False

        if self.postEditing:
            return True

        elif self.posting == 0 and len(contents) > 0:
            return await self.cancelCheck()

        return True

    async def cancelCheck(self):
        return await questionBoxAsync(
            'Blog post',
            'Cancel ?')

    async def postCancelled(self):
        self.tabRemove()
