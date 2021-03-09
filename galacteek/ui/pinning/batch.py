import functools

from PyQt5.QtCore import Qt

from PyQt5.QtWidgets import QCheckBox
from PyQt5.QtWidgets import QTableWidgetItem
from PyQt5.QtWidgets import QHeaderView
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QAbstractItemView

from galacteek.ipfs import ipfsOp

from ..widgets import GalacteekTab
from ..forms.ui_batchpinlist import Ui_BatchPinList
from ..i18n import *


class PinBatchTab(GalacteekTab):
    pass


class PinBatchWidget(QWidget):
    COL_PATH = 0
    COL_NOPIN = 1
    COL_SPIN = 2
    COL_RPIN = 3

    def __init__(self, basePath, pathList, parent=None):
        super(PinBatchWidget, self).__init__(parent)

        self.basePath = basePath
        self.pathList = pathList
        self._pinTask = None

        self.ui = Ui_BatchPinList()
        self.ui.setupUi(self)

        self.ui.labelBasePath.setText(
            'Base IPFS path: <b>{p}</b>'.format(p=str(self.basePath)))

        horizHeader = self.ui.tableWidget.horizontalHeader()
        horizHeader.sectionClicked.connect(self.onHorizSectionClicked)
        horizHeader.setSectionResizeMode(QHeaderView.ResizeToContents)
        self.ui.tableWidget.setHorizontalHeaderLabels(
            [iPath(), iDoNotPin(), iPinSingle(), iPinRecursive()])

        self.ui.tableWidget.verticalHeader().hide()
        self.ui.tableWidget.setRowCount(len(self.pathList))

        self.ui.proceedButton.clicked.connect(self.onPinObjects)
        self.ui.cancelButton.clicked.connect(self.onCancel)
        self.ui.cancelButton.hide()
        self.insertItems()

    def insertItems(self):
        added = []
        for path in self.pathList:
            if path.objPath in added:
                continue

            curRow = len(added)

            if len(path.objPath) > 92:
                text = path.objPath[0:92] + '...'
            else:
                text = path.objPath

            pItem = QTableWidgetItem(text)

            pItem.setData(Qt.UserRole, path.objPath)
            pItem.setToolTip(path.objPath)
            pItem.setFlags(
                Qt.ItemIsSelectable | Qt.ItemIsEnabled)

            checkBoxN = QCheckBox(self)
            checkBoxS = QCheckBox(self)
            checkBoxR = QCheckBox(self)

            self.ui.tableWidget.setItem(curRow, self.COL_PATH, pItem)
            self.ui.tableWidget.setCellWidget(
                curRow, self.COL_NOPIN, checkBoxN)
            self.ui.tableWidget.setCellWidget(curRow, self.COL_SPIN, checkBoxS)
            self.ui.tableWidget.setCellWidget(curRow, self.COL_RPIN, checkBoxR)

            checkBoxN.stateChanged.connect(
                functools.partial(self.noPinChecked, pItem.row()))
            checkBoxS.stateChanged.connect(
                functools.partial(self.pinSingleChecked, pItem.row()))
            checkBoxR.stateChanged.connect(
                functools.partial(self.pinRecursiveChecked, pItem.row()))
            checkBoxS.setCheckState(Qt.Checked)
            added.append(path.objPath)

        self.ui.tableWidget.setRowCount(len(added))

    def onHorizSectionClicked(self, section):
        if section in [self.COL_NOPIN, self.COL_SPIN, self.COL_RPIN]:
            for row in range(self.ui.tableWidget.rowCount()):
                item = self.ui.tableWidget.cellWidget(row, section)
                if item:
                    item.setCheckState(Qt.Checked)

    def disableAdjacent(self, row, col, state):
        adjacent = self.ui.tableWidget.cellWidget(row, col)
        if adjacent and state == Qt.Checked:
            adjacent.setCheckState(Qt.Unchecked)

    def noPinChecked(self, row, state):
        self.disableAdjacent(row, self.COL_SPIN, state)
        self.disableAdjacent(row, self.COL_RPIN, state)

    def pinSingleChecked(self, row, state):
        self.disableAdjacent(row, self.COL_NOPIN, state)
        self.disableAdjacent(row, self.COL_RPIN, state)

    def pinRecursiveChecked(self, row, state):
        self.disableAdjacent(row, self.COL_NOPIN, state)
        self.disableAdjacent(row, self.COL_SPIN, state)

    def onPinObjects(self):
        self.ui.proceedButton.setText(iPinning() + ' ...')
        self.ui.proceedButton.setEnabled(False)
        self._pinTask = ensure(self.pinSelectedObjects(),
                               futcallback=self.onPinFinished)
        self.ui.cancelButton.show()

    def onPinFinished(self, future):
        try:
            self.ui.cancelButton.hide()
            self.ui.proceedButton.setText('Done')
        except:
            pass

    def onCancel(self):
        if self._pinTask:
            self._pinTask.cancel()

        self.parentWidget().close()

    @ipfsOp
    async def pinSelectedObjects(self, ipfsop):
        def disableRow(pItem, *boxes):
            pItem.setFlags(Qt.NoItemFlags)
            [box.setEnabled(False) for box in boxes]

        for row in range(self.ui.tableWidget.rowCount()):
            pItem = self.ui.tableWidget.item(row, self.COL_PATH)
            noPinBox = self.ui.tableWidget.cellWidget(row, self.COL_NOPIN)
            pSingleBox = self.ui.tableWidget.cellWidget(row, self.COL_SPIN)
            pRecBox = self.ui.tableWidget.cellWidget(row, self.COL_RPIN)

            self.ui.tableWidget.scrollToItem(
                pItem, QAbstractItemView.PositionAtCenter)

            path = pItem.data(Qt.UserRole)
            if not path or noPinBox.isChecked():
                await ipfsop.sleep(0.3)
                disableRow(pItem, noPinBox, pSingleBox, pRecBox)
                continue

            if pSingleBox.isChecked() or pRecBox.isChecked():
                await ipfsop.ctx.pin(
                    path, recursive=pRecBox.isChecked(),
                    qname='browser-batch')
                disableRow(pItem, noPinBox, pSingleBox, pRecBox)

            await ipfsop.sleep(0.3)
