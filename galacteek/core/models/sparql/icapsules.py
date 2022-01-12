from PyQt5.QtCore import QVariant
from PyQt5.QtCore import Qt

from galacteek.ui.helpers import getIcon

from . import SparQLListModel


class ICapsulesSparQLModel(SparQLListModel):
    def data(self, QModelIndex, role=None):
        row = QModelIndex.row()

        try:
            item = self._results[row]
        except KeyError:
            return QVariant(None)
        except IndexError:
            return QVariant(None)

        try:
            if role == Qt.DisplayRole:
                roleName = b'uri'

                return str(item[roleName.decode()])
            elif role == Qt.ToolTipRole:
                roleName = b'description'

                return str(item[roleName.decode()])
            elif role == Qt.DecorationRole:
                return getIcon('capsules/icapsule-green.png')
        except Exception:
            return QVariant(None)

        else:
            return QVariant(None)
