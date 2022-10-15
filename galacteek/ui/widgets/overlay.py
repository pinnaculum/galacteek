from PyQt5.QtWidgets import QWidget

from PyQt5.QtCore import QEvent
from PyQt5.QtCore import Qt

from . import AnimatedLabel
from ..clips import RotatingCubeClipSimple


class OverlayWidget(QWidget):
    """
    Overlay a widget on top of another QWidget
    """
    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_AlwaysStackOnTop)
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Dialog)

        if parent:
            self.installEventFilter(self)

        self.raise_()

    def event(self, event: QEvent):
        if event.type() == QEvent.ParentAboutToChange:
            if self.parent():
                self.parent().removeEventFilter(self)
        elif event.type() == QEvent.ParentChange and 0:
            pass

        self.parent().lower()
        self.raise_()

        return super().event(event)

    def eventFilter(self, obj, event):
        if obj is self.parent():
            if event.type() == QEvent.Resize:
                self.resize(event.size())
            elif event.type() == QEvent.ChildAdded:
                pass

        return super().eventFilter(obj, event)


class LoadingOverlayWidget(OverlayWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.animation = AnimatedLabel(RotatingCubeClipSimple(),
                                       parent=self)

    def loading(self, progress: int = 100):
        self.animation.startClip()
        self.animation.clip.setSpeed(max(progress * 2, 150))
