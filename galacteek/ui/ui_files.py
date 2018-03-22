# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file './galacteek/ui/files.ui'
#
# Created by: PyQt5 UI code generator 5.10
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_FilesForm(object):
    def setupUi(self, FilesForm):
        FilesForm.setObjectName("FilesForm")
        FilesForm.resize(618, 349)
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(FilesForm)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setSizeConstraint(QtWidgets.QLayout.SetDefaultConstraint)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.addFileButton = QtWidgets.QToolButton(FilesForm)
        self.addFileButton.setMaximumSize(QtCore.QSize(32, 32))
        self.addFileButton.setText("")
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(":/share/icons/add-file.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.addFileButton.setIcon(icon)
        self.addFileButton.setIconSize(QtCore.QSize(32, 32))
        self.addFileButton.setObjectName("addFileButton")
        self.horizontalLayout_2.addWidget(self.addFileButton)
        self.addDirectoryButton = QtWidgets.QToolButton(FilesForm)
        icon1 = QtGui.QIcon()
        icon1.addPixmap(QtGui.QPixmap(":/share/icons/add-folder.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.addDirectoryButton.setIcon(icon1)
        self.addDirectoryButton.setIconSize(QtCore.QSize(32, 32))
        self.addDirectoryButton.setObjectName("addDirectoryButton")
        self.horizontalLayout_2.addWidget(self.addDirectoryButton)
        self.refreshButton = QtWidgets.QToolButton(FilesForm)
        self.refreshButton.setText("")
        icon2 = QtGui.QIcon()
        icon2.addPixmap(QtGui.QPixmap(":/share/icons/refresh.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.refreshButton.setIcon(icon2)
        self.refreshButton.setIconSize(QtCore.QSize(32, 32))
        self.refreshButton.setObjectName("refreshButton")
        self.horizontalLayout_2.addWidget(self.refreshButton)
        self.horizontalLayout.addLayout(self.horizontalLayout_2)
        self.statusLabel = QtWidgets.QLabel(FilesForm)
        self.statusLabel.setMinimumSize(QtCore.QSize(200, 0))
        self.statusLabel.setText("")
        self.statusLabel.setObjectName("statusLabel")
        self.horizontalLayout.addWidget(self.statusLabel)
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.searchFiles = QtWidgets.QLineEdit(FilesForm)
        self.searchFiles.setMaximumSize(QtCore.QSize(500, 16777215))
        self.searchFiles.setObjectName("searchFiles")
        self.horizontalLayout_3.addWidget(self.searchFiles)
        self.horizontalLayout.addLayout(self.horizontalLayout_3)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.treeFiles = QtWidgets.QTreeView(FilesForm)
        self.treeFiles.setObjectName("treeFiles")
        self.verticalLayout.addWidget(self.treeFiles)
        self.verticalLayout_2.addLayout(self.verticalLayout)

        self.retranslateUi(FilesForm)
        QtCore.QMetaObject.connectSlotsByName(FilesForm)

    def retranslateUi(self, FilesForm):
        _translate = QtCore.QCoreApplication.translate
        FilesForm.setWindowTitle(_translate("FilesForm", "Form"))
        self.addFileButton.setToolTip(_translate("FilesForm", "<html><head/><body><p>Add Files</p></body></html>"))
        self.addDirectoryButton.setToolTip(_translate("FilesForm", "<html><head/><body><p>Add directory</p></body></html>"))
        self.addDirectoryButton.setText(_translate("FilesForm", "Add directory"))
        self.refreshButton.setToolTip(_translate("FilesForm", "<html><head/><body><p>Refresh</p></body></html>"))

from . import galacteek_rc
