# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file './galacteek/ui/keys.ui'
#
# Created by: PyQt5 UI code generator 5.10
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_KeysForm(object):
    def setupUi(self, KeysForm):
        KeysForm.setObjectName("KeysForm")
        KeysForm.resize(606, 407)
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout(KeysForm)
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setSizeConstraint(QtWidgets.QLayout.SetMinimumSize)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setSizeConstraint(QtWidgets.QLayout.SetMinimumSize)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.addKeyButton = QtWidgets.QPushButton(KeysForm)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.addKeyButton.sizePolicy().hasHeightForWidth())
        self.addKeyButton.setSizePolicy(sizePolicy)
        self.addKeyButton.setMinimumSize(QtCore.QSize(288, 24))
        self.addKeyButton.setMaximumSize(QtCore.QSize(288, 16777215))
        self.addKeyButton.setText("")
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(":/share/icons/key.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.addKeyButton.setIcon(icon)
        self.addKeyButton.setObjectName("addKeyButton")
        self.horizontalLayout_2.addWidget(self.addKeyButton)
        self.deleteKeyButton = QtWidgets.QPushButton(KeysForm)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.deleteKeyButton.sizePolicy().hasHeightForWidth())
        self.deleteKeyButton.setSizePolicy(sizePolicy)
        self.deleteKeyButton.setMinimumSize(QtCore.QSize(288, 23))
        self.deleteKeyButton.setMaximumSize(QtCore.QSize(288, 23))
        self.deleteKeyButton.setObjectName("deleteKeyButton")
        self.horizontalLayout_2.addWidget(self.deleteKeyButton)
        self.horizontalLayout.addLayout(self.horizontalLayout_2)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.horizontalLayout_3.addLayout(self.verticalLayout)

        self.retranslateUi(KeysForm)
        QtCore.QMetaObject.connectSlotsByName(KeysForm)

    def retranslateUi(self, KeysForm):
        _translate = QtCore.QCoreApplication.translate
        KeysForm.setWindowTitle(_translate("KeysForm", "Form"))
        self.addKeyButton.setToolTip(_translate("KeysForm", "<html><head/><body><p>Create new key</p></body></html>"))
        self.deleteKeyButton.setToolTip(_translate("KeysForm", "<html><head/><body><p>Delete selected key</p></body></html>"))
        self.deleteKeyButton.setText(_translate("KeysForm", "Delete"))

from . import galacteek_rc
