# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file './galacteek/ui/mediaplayer.ui'
#
# Created by: PyQt5 UI code generator 5.10
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_MediaPlayer(object):
    def setupUi(self, MediaPlayer):
        MediaPlayer.setObjectName("MediaPlayer")
        MediaPlayer.resize(400, 300)
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(MediaPlayer)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.verticalLayout_2.addLayout(self.verticalLayout)

        self.retranslateUi(MediaPlayer)
        QtCore.QMetaObject.connectSlotsByName(MediaPlayer)

    def retranslateUi(self, MediaPlayer):
        _translate = QtCore.QCoreApplication.translate
        MediaPlayer.setWindowTitle(_translate("MediaPlayer", "Form"))

