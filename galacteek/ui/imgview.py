import functools

from PyQt5.QtCore import Qt
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QCoreApplication

from PyQt5.QtGui import QImage
from PyQt5.QtGui import QPixmap
from PyQt5.QtGui import QPalette
from PyQt5.QtGui import QKeySequence

from PyQt5.Qt import QSizePolicy

from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QScrollArea
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QToolButton
from PyQt5.QtWidgets import QSpacerItem
from PyQt5.QtWidgets import QLayout

from galacteek import ensure
from galacteek import logUser
from galacteek.crypto.qrcode import IPFSQrDecoder
from galacteek.ipfs.wrappers import ipfsOp

from .widgets import GalacteekTab
from .helpers import getIcon
from .clipboard import iCopyToClipboard
from .i18n import iZoomIn
from .i18n import iZoomOut
from .i18n import iOpen


def iImageGotQrCodes(count):
    return QCoreApplication.translate(
        'ImageView',
        'This image contains {} valid IPFS QR code(s) !').format(
            count)


class ImageViewerTab(GalacteekTab):
    def __init__(self, imgPath, mainW):
        super().__init__(mainW)

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

        layout = QHBoxLayout()
        layout.addItem(
            QSpacerItem(10, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        layout.addWidget(self.zoomOut, 0, Qt.AlignLeft)
        layout.addWidget(self.zoomIn, 0, Qt.AlignLeft)
        layout.addWidget(self.fitWindow, 0, Qt.AlignLeft)

        self.vLayout.addLayout(layout)

        self.view = ImageView(self)
        self.view.imageLoaded.connect(self.onImageLoaded)
        self.view.qrCodesPresent.connect(self.onQrCodesListed)
        self.vLayout.addWidget(self.view)

        self.zoomIn.clicked.connect(self.view.zoomIn)
        self.zoomOut.clicked.connect(self.view.zoomOut)
        self.fitWindow.clicked.connect(
            lambda: self.view.fitWindow(self.fitWindow.isChecked()))

        ensure(self.view.showImage(imgPath))

    def onImageLoaded(self, path):
        pass

    def onQrCodesListed(self, urls):
        # Create the scroll area and fix maximum height
        # TODO: set maximum size on resize as well
        scrollArea = QScrollArea()
        scrollArea.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding)
        scrollArea.setWidgetResizable(True)
        scrollArea.setMaximumHeight(self.height() / 3)

        frame = QFrame(scrollArea)
        frame.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = QVBoxLayout()
        layout.setSizeConstraint(QLayout.SetMinAndMaxSize)

        scrollArea.setWidget(frame)

        iconOpen = getIcon('open.png')
        lbl = QLabel()
        lbl.setText(iImageGotQrCodes(len(urls)))
        lbl.setObjectName('qrCodeCountLabel')
        lbl.setStyleSheet('QLabel { font-size: 14pt; text-align: center; }')
        layout.addWidget(lbl)
        layout.addItem(
            QSpacerItem(10, 10, QSizePolicy.Minimum, QSizePolicy.Minimum))

        def onOpenItem(url):
            ensure(self.app.resourceOpener.open(url))

        for url in urls:
            hLayout = QHBoxLayout()
            hLayout.setSizeConstraint(QLayout.SetMinAndMaxSize)

            lbl = QLabel()
            lbl.setText('<b>{}</b>'.format(url))
            lbl.setStyleSheet('QLabel { font-size: 12pt }')

            clipBtn = QToolButton()
            clipBtn.setIcon(getIcon('clipboard.png'))
            clipBtn.setToolTip(iCopyToClipboard())
            clipBtn.clicked.connect(
                functools.partial(self.app.setClipboardText, url))

            openBtn = QToolButton()
            openBtn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            openBtn.setIcon(iconOpen)
            openBtn.setText(iOpen())
            openBtn.clicked.connect(functools.partial(onOpenItem, url))

            hLayout.addWidget(lbl)
            hLayout.addWidget(openBtn)
            hLayout.addWidget(clipBtn)
            layout.addLayout(hLayout)

        frame.setLayout(layout)
        self.vLayout.addWidget(scrollArea)


class ImageView(QScrollArea):
    imageLoaded = pyqtSignal(str)
    qrCodesPresent = pyqtSignal(list)

    def __init__(self, parent=None):
        super(ImageView, self).__init__(parent)

        self.setObjectName('ImageView')
        self.qrDecoder = IPFSQrDecoder()
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

            self.imageLoaded.emit(imgPath)

            if self.qrDecoder:
                # See if we have any QR codes in the image
                urls = self.qrDecoder.decode(imgData)
                if urls:
                    self.qrCodesPresent.emit(urls)

        except Exception:
            logUser.debug('Failed to load image: {path}'.format(
                path=imgPath))
