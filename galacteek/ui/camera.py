import time
import os.path
from pathlib import Path
import shutil

from PyQt5.QtWidgets import QToolButton
from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QActionGroup
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtWidgets import QMenu
from PyQt5.QtWidgets import QApplication

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import QByteArray
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import QBuffer
from PyQt5.QtCore import QIODevice

from PyQt5.QtGui import QPixmap

from PyQt5.QtMultimedia import QCamera
from PyQt5.QtMultimedia import QCameraImageCapture
from PyQt5.QtMultimedia import QMediaRecorder

from galacteek import log
from galacteek import ensure
from galacteek.ui.widgets import PopupToolButton
from galacteek.ui.helpers import getIcon
from galacteek.ui.helpers import messageBox
from galacteek.ui.helpers import questionBox
from galacteek.ui.helpers import inputTextCustom
from galacteek.ipfs import ipfsOp

from . import ui_camera


def iWebcamIpfsCapture():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Capture images and record videos to IPFS'
    )


def iCapture():
    return QCoreApplication.translate(
        'GalacteekWindow', 'Capture')


def iDevices():
    return QCoreApplication.translate(
        'GalacteekWindow', 'Devices')


class CameraController(PopupToolButton):
    def __init__(self, parent=None):
        super(CameraController, self).__init__(
            icon=getIcon('camera.png'),
            mode=QToolButton.InstantPopup,
            parent=parent
        )

        self.setToolTip(iWebcamIpfsCapture())

        self.menuDevices = QMenu(iDevices())
        self.menuDevices.setIcon(self.icon())

        self.menu.addMenu(self.menuDevices)
        self.menu.addSeparator()

        self.captureAction = QAction(
            self.icon(),
            iCapture(),
            self,
            triggered=self.onCameraView
        )
        self.captureAction.setEnabled(False)

        self.menu.addAction(self.captureAction)
        self.camView = None

        self.videoDevicesGroup = QActionGroup(self)
        self.videoDevicesGroup.setExclusive(True)

        self.detectDevices()

    def detectDevices(self):
        cameraDevice = QByteArray()

        for name in QCamera.availableDevices():
            description = QCamera.deviceDescription(name)
            deviceAction = QAction(description, self.videoDevicesGroup)
            deviceAction.setCheckable(True)
            deviceAction.setData(name)

            if cameraDevice.isEmpty():
                cameraDevice = name
                deviceAction.setChecked(True)

            self.menuDevices.addAction(deviceAction)

        self.videoDevicesGroup.triggered.connect(self.changeCameraDevice)
        self.setCamera(cameraDevice)

    def changeCameraDevice(self, action):
        cameraName = action.data()
        log.debug(f'Using camera: {cameraName}')

        self.setCamera(cameraName)

    def setCamera(self, cameraDevice):
        if cameraDevice.isEmpty():
            self.camera = QCamera()
        else:
            self.camera = QCamera(cameraDevice)

        self.captureAction.setEnabled(True)

    def onCameraView(self):
        if self.camView and self.camView.isVisible():
            return

        if self.camView:
            self.camView.close()
            del self.camView

        self.camView = CameraView(self.camera)
        self.camera.setViewfinder(self.camView.ui.viewfinder)

        self.camView.show()
        self.camera.start()


class CameraView(QMainWindow):
    """
    Camera view widget

    .ui form is based on pyqt5/examples/multimediawidgets/camera
    """

    def __init__(self, camera, parent=None):
        super(CameraView, self).__init__(parent)

        self.app = QApplication.instance()
        self.camera = camera

        self.ui = ui_camera.Ui_CameraView()
        self.ui.setupUi(self)

        self.setWindowTitle(iWebcamIpfsCapture())

        self.camera.setCaptureMode(QCamera.CaptureStillImage)
        self.camera.stateChanged.connect(self.onCameraStateChange)
        self.camera.error.connect(self.onCameraError)

        # Image capture
        self.imageCapture = QCameraImageCapture(self.camera)
        self.imageCapture.setCaptureDestination(
            QCameraImageCapture.CaptureToBuffer)
        self.imageCapture.imageCaptured.connect(
            lambda reqid, img: ensure(self.handleImage(reqid, img)))
        self.imageCapture.readyForCaptureChanged.connect(self.readyForCapture)

        # Recorder
        self.mediaRecorder = QMediaRecorder(self.camera)
        self.mediaRecorder.durationChanged.connect(self.recDurationChanged)
        self.mediaRecorder.stateChanged.connect(self.updateRecorderState)
        self.mediaRecorder.actualLocationChanged.connect(
            self.recLocationChanged)
        self.mediaRecorder.error.connect(self.onRecorderError)

        self.ui.captureWidget.currentChanged.connect(self.updateCaptureMode)
        self.ui.captureImageButton.clicked.connect(self.captureImage)
        self.ui.closeButton.clicked.connect(self.onClose)
        self.ui.recordButton.clicked.connect(self.record)
        self.ui.pauseButton.clicked.connect(self.pause)
        self.ui.stopButton.clicked.connect(self.stop)
        self.ui.muteButton.toggled.connect(self.setMuted)
        self.ui.pauseButton.hide()

        self.isCapturingImage = False
        self.videoLocation = None

        self.showMaximized()

    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            return

        if event.key() == Qt.Key_Escape:
            self.camera.stop()
            self.hide()
            event.accept()
        elif event.key() == Qt.Key_S:
            if self.camera.captureMode() == QCamera.CaptureStillImage:
                self.captureImage()
            event.accept()
        else:
            super(CameraView, self).keyPressEvent(event)

    async def handleImage(self, requestId, img):
        scaledImage = img.scaled(
            self.ui.viewfinder.size(), Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        self.ui.lastImagePreviewLabel.setPixmap(QPixmap.fromImage(scaledImage))
        self.displayCapturedImage()

        imgFormat = self.ui.captureImageFormat.currentText()

        array = QByteArray()
        buffer = QBuffer(array)
        buffer.open(QIODevice.WriteOnly)
        scaledImage.save(buffer, imgFormat)
        buffer.close()

        await self.importImageBuffer(buffer, imgFormat.lower())

        QTimer.singleShot(3000, self.displayViewfinder)

    def recLocationChanged(self, loc):
        pass

    def record(self):
        self.mediaRecorder.record()
        self.videoLocation = self.mediaRecorder.outputLocation()
        self.updateRecordTime()

    def pause(self):
        self.mediaRecorder.pause()

    def stop(self):
        self.mediaRecorder.stop()
        self.ui.statusbar.showMessage('')

        if self.videoLocation and questionBox(
                'Video import', 'Import video to your repository ?'):

            filePath = self.videoLocation.toLocalFile()

            if not os.path.isfile(filePath):
                return messageBox('Could not find captured video')

            basename = os.path.basename(filePath)

            name = inputTextCustom(
                'Video import', 'Video filename',
                text=basename
            )

            if not name:
                return

            if name != basename:
                dst = Path(os.path.dirname(filePath)).joinpath(name)
                shutil.move(filePath, str(dst))
            else:
                dst = Path(filePath)

            if name:
                ensure(self.importVideoRecord(dst, name))

    @ipfsOp
    async def importImageBuffer(self, ipfsop, buffer, extension):
        fModel = ipfsop.ctx.currentProfile.filesModel

        entry = await ipfsop.addBytes(
            bytes(buffer.data()),
            pin=self.ui.pinCapturedPhoto.isChecked()
        )

        if entry:
            if self.ui.copyPhotoToMfs.isChecked():
                await ipfsop.filesLink(
                    entry, fModel.itemPictures.path,
                    name='camshot-{id}.{ext}'.format(
                        id=int(time.time()),
                        ext=extension
                    )
                )

                self.app.mainWindow.fileManagerWidget.refreshItem(
                    fModel.itemPictures
                )

            if self.ui.copyPhotoCidToClipboard.isChecked():
                self.app.setClipboardText(entry['Hash'])
        else:
            messageBox('Could not import image')

    @ipfsOp
    async def importVideoRecord(self, ipfsop, videoPath, name):
        fModel = ipfsop.ctx.currentProfile.filesModel

        entry = await ipfsop.addPath(
            str(videoPath), wrap=True,
            pin=self.ui.pinVideo.isChecked()
        )

        if entry:
            # Can remove it from disk now

            try:
                videoPath.unlink()
            except Exception:
                log.debug(f'Could not remove video {videoPath}')

            if self.ui.copyVideoToMfs.isChecked():
                await ipfsop.filesLink(
                    entry, fModel.itemVideos.path,
                    name=f'{name}.dirw'
                )

                self.app.mainWindow.fileManagerWidget.refreshItem(
                    fModel.itemVideos
                )

            if self.ui.copyVideoCidToClipboard.isChecked():
                try:
                    # Copy the video's CID
                    listing = await ipfsop.listObject(entry['Hash'])
                    links = listing['Objects'].pop()['Links']
                    videoCid = links.pop()['Hash']
                    self.app.setClipboardText(videoCid)
                except Exception:
                    # Fall back to copying the directory wrapper
                    self.app.setClipboardText(entry['Hash'])
        else:
            messageBox('Could not import video')

    def setMuted(self, muted):
        self.mediaRecorder.setMuted(muted)

    def captureImage(self):
        self.isCapturingImage = True
        self.imageCapture.capture()

    def updateCaptureMode(self):
        tabIndex = self.ui.captureWidget.currentIndex()
        captureMode = QCamera.CaptureStillImage if tabIndex == 0 else \
            QCamera.CaptureVideo

        if self.camera.isCaptureModeSupported(captureMode):
            self.camera.setCaptureMode(captureMode)

    def onCameraStateChange(self, state):
        if state == QCamera.ActiveState:
            pass
        elif state in (QCamera.UnloadedState, QCamera.LoadedState):
            pass

    def updateRecorderState(self, state):
        if state == QMediaRecorder.StoppedState:
            self.ui.recordButton.setEnabled(True)
            self.ui.pauseButton.setEnabled(True)
            self.ui.stopButton.setEnabled(False)
        elif state == QMediaRecorder.PausedState:
            self.ui.recordButton.setEnabled(True)
            self.ui.pauseButton.setEnabled(False)
            self.ui.stopButton.setEnabled(True)
        elif state == QMediaRecorder.RecordingState:
            self.ui.recordButton.setEnabled(False)
            self.ui.pauseButton.setEnabled(True)
            self.ui.stopButton.setEnabled(True)

    def onRecorderError(self):
        messageBox('Capture Error: {}'.format(
            self.mediaRecorder.errorString()))

    def onCameraError(self):
        messageBox('Camera Error: {}'.format(
            self.camera.errorString()))

    def recDurationChanged(self, duration):
        self.updateRecordTime()

    def updateRecordTime(self):
        msg = "Recorded {secs} secs".format(
            secs=self.mediaRecorder.duration() // 1000)
        self.ui.statusbar.showMessage(msg)

    def displayViewfinder(self):
        self.ui.stackedWidget.setCurrentIndex(0)

    def displayCapturedImage(self):
        self.ui.stackedWidget.setCurrentIndex(1)

    def readyForCapture(self, ready):
        self.ui.captureImageButton.setEnabled(ready)

    def onClose(self):
        self.camera.stop()
        self.hide()

    def closeEvent(self, event):
        self.camera.stop()
        super().closeEvent(event)
