
from PyQt5.QtCore import Qt

from PyQt5.QtGui import QImage
from PyQt5.QtGui import QPixmap
from PyQt5.QtGui import QPalette
from PyQt5.QtGui import QKeySequence

from PyQt5.Qt import QSizePolicy

from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QScrollArea
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QToolButton
from PyQt5.QtWidgets import QSpacerItem

from galacteek.ipfs.wrappers import ipfsOp
from galacteek import ensure
from galacteek import logUser

from .widgets import GalacteekTab
from .helpers import getIcon
from .i18n import iZoomIn
from .i18n import iZoomOut


class ImageViewerTab(GalacteekTab):
    def __init__(self, imgPath, mainW):
        super().__init__(mainW)

        layout = QHBoxLayout()
        self.zoomIn = QToolButton()
        self.zoomIn.setIcon(getIcon('zoom-in.png'))
        self.zoomIn.setShortcut(QKeySequence('Ctrl++'))
        self.zoomIn.setToolTip(iZoomIn())
        self.zoomOut = QToolButton()
        self.zoomOut.setIcon(getIcon('zoom-out.png'))
        self.zoomOut.setShortcut(QKeySequence('Ctrl+-'))
        self.zoomOut.setToolTip(iZoomOut())

        self.fitWindow = QToolButton()
        self.fitWindow.setCheckable(True)
        self.fitWindow.setToolTip('Fit to window')
        self.fitWindow.setIcon(getIcon('expand.png'))

        layout.addItem(
            QSpacerItem(10, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        layout.addWidget(self.zoomOut, 0, Qt.AlignLeft)
        layout.addWidget(self.zoomIn, 0, Qt.AlignLeft)
        layout.addWidget(self.fitWindow, 0, Qt.AlignLeft)

        self.vLayout.addLayout(layout)

        self.view = ImageView(self)
        self.vLayout.addWidget(self.view)

        self.zoomIn.clicked.connect(self.view.zoomIn)
        self.zoomOut.clicked.connect(self.view.zoomOut)
        self.fitWindow.clicked.connect(
            lambda: self.view.fitWindow(self.fitWindow.isChecked()))

        ensure(self.view.showImage(imgPath))


class ImageView(QScrollArea):
    def __init__(self, parent=None):
        super(ImageView, self).__init__(parent)

        self.image = QImage()
        self.labelImage = QLabel(self)
        self.setAlignment(Qt.AlignCenter)

        self.setBackgroundRole(QPalette.Dark)
        self.labelImage.setSizePolicy(
            QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.labelImage.setScaledContents(True)
        self.scaleFactor = 1.0
        self.setWidget(self.labelImage)

    def fitWindow(self, fit):
        self.setWidgetResizable(fit)

        if not fit:
            self.scaleFactor = 1.0
            self.resizePixmap()

    def zoomOut(self):
        self.scaleFactor *= 0.75
        self.resizePixmap()

    def zoomIn(self):
        self.scaleFactor *= 1.25
        self.resizePixmap()

    def resizePixmap(self):
        self.labelImage.resize(
            self.scaleFactor * self.labelImage.pixmap().size())

    @ipfsOp
    async def showImage(self, ipfsop, imgPath):
        try:
            imgData = await ipfsop.waitFor(
                ipfsop.client.cat(imgPath), 8
            )

            if not imgData:
                raise Exception('Failed to load image')

            img = QImage()
            img.loadFromData(imgData)
            self.image = img

            self.labelImage.setPixmap(QPixmap.fromImage(self.image))
            self.labelImage.adjustSize()
            self.resizePixmap()
        except Exception:
            logUser.debug('Failed to load image: {path}'.format(
                path=imgPath))
