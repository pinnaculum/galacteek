from pathlib import Path

from PyQt5.QtCore import QUrl
from PyQt5.QtQuick import QQuickView
from PyQt5.QtQuickWidgets import QQuickWidget

from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.core import runningApp
from galacteek.core import pkgResourcesRscFilename


def quickWidget(url, parent=None):
    if isinstance(url, QUrl):
        return QQuickWidget(url, parent)
    elif isinstance(url, str):
        return QQuickWidget(QUrl(url), parent)


def quickEnginedWidget(engine, url, parent=None):
    qWidget = QQuickWidget(engine, parent)
    qWidget.setSource(url)
    return qWidget


def quickWidgetFromIpfs(ipfsPath: IPFSPath, parent=None):
    app = runningApp()

    url = app.subUrl(str(ipfsPath))
    parentUrl = app.subUrl(str(ipfsPath.parent()))

    qWidget = QQuickWidget(parent)
    qWidget.engine().setBaseUrl(parentUrl)
    qWidget.setSource(url)
    return qWidget


def quickWidgetFromFile(fp: str, parent=None,
                        show: bool = True):
    qWidget = QQuickWidget(parent)
    qWidget.setSource(QUrl.fromLocalFile(fp))

    if show:
        qWidget.show()

    return qWidget


def quickWidgetFromLibrary(rel: str, parent=None):
    """
    Load a QML file from the common library

    :param str rel: Relative path to the QML file inside the library dir
    """

    libraryRoot = Path(pkgResourcesRscFilename('galacteek.qml', 'dweb_lib'))

    return quickWidgetFromFile(str(
        libraryRoot.joinpath(rel)),
        parent=parent
    )


def quickView(url: str, parent=None):
    view = QQuickView(parent)
    view.setResizeMode(QQuickView.SizeRootObjectToView)

    view.setSource(QUrl(url))
    view.show()
    return view
