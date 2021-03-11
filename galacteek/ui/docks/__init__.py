from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QDockWidget


class SpaceDock(QDockWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName('dockBase')
        self.setTitleBarWidget(QWidget())
        self.setFeatures(QDockWidget.NoDockWidgetFeatures)

    def dockIt(self, widget):
        self.widget().layout().addWidget(widget)

    def dockItAt(self, index, widget):
        self.widget().layout().insertWidget(index, widget)
