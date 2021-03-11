from distutils.version import StrictVersion

from PyQt5 import QtWebEngine

from PyQt5.QtWebEngineWidgets import QWebEnginePage  # noqa
from PyQt5.QtWebEngineWidgets import QWebEngineDownloadItem  # noqa
from PyQt5.QtWebEngineWidgets import QWebEngineSettings  # noqa
from PyQt5.QtWebEngineWidgets import QWebEngineContextMenuData  # noqa
from PyQt5.QtWebEngineWidgets import QWebEngineProfile  # noqa
from PyQt5.QtWebEngineWidgets import QWebEngineSettings  # noqa
from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor  # noqa
from PyQt5.QtWebChannel import QWebChannel  # noqa


webEngineV513_0 = StrictVersion('5.13.0')
webEngineV514_0 = StrictVersion('5.14.0')
webEngineV515_0 = StrictVersion('5.15.0')
webEngineV515_2 = StrictVersion('5.15.2')


def webEngineVersion():
    return StrictVersion(QtWebEngine.PYQT_WEBENGINE_VERSION_STR)


def webEngine515():
    return webEngineVersion() >= webEngineV515_0


def webEngine513():
    version = webEngineVersion()
    return version >= webEngineV513_0 and version < webEngineV514_0
