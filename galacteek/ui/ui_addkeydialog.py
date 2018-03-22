# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file './galacteek/ui/addkeydialog.ui'
#
# Created by: PyQt5 UI code generator 5.10
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_AddKeyDialog(object):
    def setupUi(self, AddKeyDialog):
        AddKeyDialog.setObjectName("AddKeyDialog")
        AddKeyDialog.resize(436, 295)
        self.buttonBox = QtWidgets.QDialogButtonBox(AddKeyDialog)
        self.buttonBox.setGeometry(QtCore.QRect(60, 180, 341, 32))
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.label = QtWidgets.QLabel(AddKeyDialog)
        self.label.setGeometry(QtCore.QRect(20, 30, 121, 16))
        self.label.setObjectName("label")
        self.keyName = QtWidgets.QLineEdit(AddKeyDialog)
        self.keyName.setGeometry(QtCore.QRect(130, 30, 251, 23))
        self.keyName.setObjectName("keyName")
        self.label_2 = QtWidgets.QLabel(AddKeyDialog)
        self.label_2.setGeometry(QtCore.QRect(20, 100, 59, 15))
        self.label_2.setObjectName("label_2")
        self.keySize = QtWidgets.QComboBox(AddKeyDialog)
        self.keySize.setGeometry(QtCore.QRect(130, 100, 79, 23))
        self.keySize.setObjectName("keySize")
        self.keySize.addItem("")
        self.keySize.addItem("")

        self.retranslateUi(AddKeyDialog)
        self.buttonBox.accepted.connect(AddKeyDialog.accept)
        self.buttonBox.rejected.connect(AddKeyDialog.reject)
        QtCore.QMetaObject.connectSlotsByName(AddKeyDialog)

    def retranslateUi(self, AddKeyDialog):
        _translate = QtCore.QCoreApplication.translate
        AddKeyDialog.setWindowTitle(_translate("AddKeyDialog", "Dialog"))
        self.label.setText(_translate("AddKeyDialog", "Key name"))
        self.label_2.setText(_translate("AddKeyDialog", "Key size"))
        self.keySize.setItemText(0, _translate("AddKeyDialog", "2048"))
        self.keySize.setItemText(1, _translate("AddKeyDialog", "4096"))

