from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QModelIndex
from PyQt5.QtCore import QStringListModel


from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QCompleter


class LDCompleter(QCompleter):
    pass


class LDSearcher(QLineEdit):
    """
    Linked-data searcher (looks up dbpedia and others)
    """

    cancelled = pyqtSignal()
    resultActivated = pyqtSignal(QModelIndex)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.completer = LDCompleter(self)
        self.completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setCompletionColumn(0)
        self.completer.activated[QModelIndex].connect(self.onResultActivated)

        self.setCompleter(self.completer)

    @property
    def model(self):
        return self.completer.model()

    def resetModel(self):
        self.completer.setModel(QStringListModel([]))

    def feedModel(self, model, popup=True):
        self.completer.setModel(model)

        if popup:
            self.completer.complete()

    def onResultActivated(self, idx: QModelIndex):
        self.resultActivated.emit(idx)
