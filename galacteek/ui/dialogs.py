
import time

from PyQt5.QtWidgets import (QWidget, QApplication,
        QDialog, QLabel, QTextEdit, QPushButton, QMessageBox)

from PyQt5.QtCore import QUrl, Qt, pyqtSlot

from . import ui_addkeydialog, ui_addbookmarkdialog

class AddBookmarkDialog(QDialog):
    def __init__(self, bookmarks, resource, title, parent=None):
        super().__init__(parent)

        self.ipfsResource = resource
        self.bookmarks = bookmarks

        self.ui = ui_addbookmarkdialog.Ui_AddBookmarkDialog()
        self.ui.setupUi(self)
        self.ui.resourceLabel.setText(self.ipfsResource)
        self.ui.title.setText(title)

        for cat in self.bookmarks.getCategories():
            self.ui.category.addItem(cat)

    def accept(self):
        self.bookmarks.add(self.ipfsResource,
            self.ui.title.text(), category=self.ui.category.currentText())
        self.done(0)
