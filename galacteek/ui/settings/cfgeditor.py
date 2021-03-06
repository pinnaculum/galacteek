import asyncio

from PyQt5.QtWidgets import QTreeWidget
from PyQt5.QtWidgets import QTreeWidgetItem
from PyQt5.QtWidgets import QHeaderView
from PyQt5.QtWidgets import QStyledItemDelegate
from PyQt5.QtWidgets import QSpinBox
from PyQt5.QtWidgets import QDoubleSpinBox
from PyQt5.QtWidgets import QComboBox
from PyQt5.QtWidgets import QLabel

from PyQt5.QtCore import Qt
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QSize
from PyQt5.QtCore import QModelIndex

from galacteek.config import configModLeafAttributes
from galacteek.config import configModules
from galacteek.config import cGet
from galacteek.config import cSet

from galacteek import ensureSafe
from galacteek import partialEnsure

from ..widgets import GalacteekTab
from ..helpers import *
from ..i18n import *


ModRole = Qt.UserRole + 1
AttrRole = Qt.UserRole + 2
AttrTypeRole = Qt.UserRole + 3


class ConfigItemDelegate(QStyledItemDelegate):
    INT_MAX = 2147483647

    attributeChanged = pyqtSignal(QModelIndex)

    def __init__(self, parent):
        super().__init__(parent)
        self.model = parent.model()
        self.tree = parent

    def _tr(self, index):
        mod = self.model.data(index, ModRole)
        attr = self.model.data(index, AttrRole)
        atype = self.model.data(index, AttrTypeRole)
        return mod, attr, atype

    def setEditorData(self, editor, index):
        mod, attr, atype = self._tr(index)
        value = cGet(attr, mod=mod)

        if isinstance(editor, QSpinBox) or isinstance(editor, QDoubleSpinBox):
            editor.setValue(value)

        if isinstance(editor, QComboBox):
            editor.setCurrentText(str(value))

    def setModelData(self, editor, model, index):
        mod, attr, atype = self._tr(index)

        if isinstance(editor, QSpinBox) or isinstance(editor, QDoubleSpinBox):
            cSet(attr, editor.value(), mod=mod)
            self.attributeChanged.emit(index)
        elif isinstance(editor, QComboBox):
            if editor.currentText() == str(True):
                cSet(attr, True, mod=mod)
            else:
                cSet(attr, False, mod=mod)
            self.attributeChanged.emit(index)

    def createEditor(self, parent, option, index):
        mod, attr, atype = self._tr(index)

        if atype is int:
            editor = QSpinBox(parent)
            editor.setMinimum(0)
            editor.setMaximum(self.INT_MAX)
            editor.setSingleStep(1)

            # Icons
            if attr.lower().endswith('iconsize'):
                editor.setSingleStep(8)
        elif atype is float:
            editor = QDoubleSpinBox(parent)
            editor.setMinimum(0)
            editor.setMaximum(float(self.INT_MAX))
            editor.setSingleStep(0.1)
        elif atype is bool:
            editor = QComboBox(parent)
            editor.addItem(str(True))
            editor.addItem(str(False))
        else:
            return None

        return editor

    def destroyEditor(self, editor, index):
        editor.deleteLater()

    def displayText(self, value, locale):
        return str(value)

    def sizeHint(self, option, index):
        return QSize(
            self.tree.width() / 8,
            32
        )


class ConfigModuleItem(QTreeWidgetItem):
    pass


class ConfigManager(GalacteekTab):
    COL_ATTR = 0
    COL_EDITOR = 1
    COL_STATUS = 2

    def tabSetup(self):
        self.setContentsMargins(8, 8, 8, 8)
        self.wLabel = QLabel(iConfigurationEditorWarning())
        self.tree = QTreeWidget(self)
        self.delegate = ConfigItemDelegate(self.tree)

        self.delegate.attributeChanged.connect(self.onAttrChanged)

        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(['Setting', 'Value', ''])
        self.tree.setHeaderHidden(True)
        self.tree.setItemDelegateForColumn(1, self.delegate)
        self.tree.itemDoubleClicked.connect(
            partialEnsure(self.onDoubleClick))
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tree.header().setStretchLastSection(False)
        self.addToLayout(self.wLabel)
        self.addToLayout(self.tree)
        self.setEnabled(False)

        ensureSafe(self.load())

    @property
    def root(self):
        return self.tree.invisibleRootItem()

    async def load(self):
        await self.loadSettings()
        self.setEnabled(True)

    async def loadSettings(self):
        self.tree.clear()

        bfont = self.font()
        bfont.setBold(True)
        bfont.setPointSize(16)

        for mod in configModules():
            modItem = ConfigModuleItem(self.root)
            modItem.setText(0, mod)
            modItem.setFont(0, bfont)

            await asyncio.sleep(0)

    def onAttrChanged(self, aIdx):
        item = self.tree.itemFromIndex(aIdx)
        if item:
            item.setText(self.COL_STATUS, 'OK')

            self.app.loop.call_later(
                2.0,
                item.setText,
                self.COL_STATUS,
                ''
            )

    async def onDoubleClick(self, modItem, col, *args):
        if not isinstance(modItem, ConfigModuleItem):
            return

        mod = modItem.text(0)

        if modItem.childCount() == 0:
            self.setEnabled(False)

            for attr in configModLeafAttributes(mod):
                value = cGet(attr, mod=mod)

                if isinstance(value, int) or isinstance(value, float):
                    item = QTreeWidgetItem(modItem)
                    item.setText(0, attr)
                    item.setText(1, str(value))

                    item.setData(1, ModRole, mod)
                    item.setData(1, AttrRole, attr)
                    item.setData(1, AttrTypeRole, type(value))

                    self.tree.openPersistentEditor(item, 1)

            modItem.setExpanded(True)
            self.setEnabled(True)
