
import os.path

from PyQt5.QtCore import (pyqtSignal, QObject)

from galacteek.ipfs.wrappers import *

class UserProfile(QObject):
    """ User profile object """

    P_FILES = 'files'

    def __init__(self, ctx, name, rootDir):
        super(UserProfile, self).__init__()

        self._ctx = ctx
        self._name = name
        self._rootDir = rootDir

        self._filesModel = None

    @property
    def root(self):
        return self._rootDir # profile's root dir in the IPFS repository

    @property
    def ctx(self):
        return self._ctx # IPFS context

    @property
    def name(self):
        return self._name

    @property
    def filesModel(self):
        return self._filesModel

    @property
    def tree(self):
        # Profile's filesystem tree list
        return [
            self.pathFiles,
            self.pathHome,
            self.pathMedia,
            self.pathPictures,
            self.pathVideos,
            self.pathMusic,
            self.pathCode,
            self.pathWebsites
        ]

    @property
    def pathFiles(self):
        return os.path.join(self.root, self.P_FILES)

    @property
    def pathConfig(self):
        return os.path.join(self.root, 'config')

    @property
    def pathHome(self):
        return os.path.join(self.pathFiles, 'home')

    @property
    def pathMedia(self):
        return os.path.join(self.pathFiles, 'multimedia')

    @property
    def pathPictures(self):
        return os.path.join(self.pathMedia, 'pictures')

    @property
    def pathVideos(self):
        return os.path.join(self.pathMedia, 'videos')

    @property
    def pathMusic(self):
        return os.path.join(self.pathMedia, 'music')

    @property
    def pathCode(self):
        return os.path.join(self.pathFiles, 'code')

    @property
    def pathWebsites(self):
        return os.path.join(self.pathFiles, 'websites')

    def setFilesModel(self, model):
        self._filesModel = model

    @ipfsOp
    async def init(self, ipfsop):
        """
        Initialize the profile's filesystem
        """

        await ipfsop.filesMkdir(self.root)

        for directory in self.tree:
            await ipfsop.filesMkdir(directory)

        # If an old profile-less files entry is found at the root,
        # move it to the home if this is the default profile
        exFiles = await ipfsop.filesLookup(GFILES_ROOT_PATH, 'myfiles')
        if exFiles and self.name == 'default':
            r = await ipfsop.filesMove(self.pathHome,
                    self.pathHome + '.old')
            r = await ipfsop.filesMove(
                    os.path.join(GFILES_ROOT_PATH, 'myfiles'),
                    self.pathHome)
