
from PyQt5.QtGui import QMovie
from PyQt5.QtGui import QIcon


class BaseClip(QMovie):
    clipname = 'rotating-cube.gif'
    speedStart = 100
    cache = True

    def __init__(self, cache=True, speed=None):
        super(BaseClip, self).__init__(f':/share/clips/{self.clipname}')

        self.setSpeed(speed if speed else self.speedStart)

        self.setCacheMode(
            QMovie.CacheAll if self.cache is True else QMovie.CacheNone)

    def createIcon(self):
        return QIcon(self.currentPixmap())

    def playing(self):
        return self.state() == QMovie.Running


class BouncyOrbitClip(BaseClip):
    clipname = 'bouncy-orbit.gif'
    speedStart = 50


class RotatingCubeClipSimple(BaseClip):
    clipname = 'rotating-cube.gif'


class BouncingCubeClip1(BaseClip):
    clipname = 'bouncing-cube-12fps.gif'
    speedStart = 220


class BouncingCubeClip2(BaseClip):
    clipname: str = 'bouncing-cube-18fps.gif'
    speedStart = 160


class RotatingCubeRedFlash140d(BaseClip):
    clipname = 'rotating-cube-redflash-140-6fps.gif'


class RotatingCubeClipFunky(BaseClip):
    clipname = 'funky-cube-1.gif'
