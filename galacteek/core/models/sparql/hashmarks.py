import html2text

from PyQt5.QtCore import QVariant
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from galacteek.ui.helpers import getIcon
from galacteek.ui.helpers import getMimeIcon

from . import SparQLListModel


HashmarkUriRole = Qt.UserRole + 1

h2text = html2text.HTML2Text()
h2text.emphasis_mark = ''


def h2t(text):
    return h2text.handle(text).replace('\n', '').strip()


class LDHashmarksSparQLModel(SparQLListModel):
    def data(self, QModelIndex, role=None):
        row = QModelIndex.row()

        try:
            item = self._results[row]
        except (KeyError, IndexError):
            return QVariant(None)

        try:
            if role == Qt.DisplayRole:
                return h2t(str(item['title']))
            elif role == HashmarkUriRole:
                return str(item['uri'])
            elif role == Qt.ToolTipRole:
                return h2t(str(item['descr']))
            elif role == Qt.FontRole:
                return QFont('Montserrat', 16)

            elif role == Qt.DecorationRole:
                mType = str(item['mimeType'])

                icon = getMimeIcon(mType)

                if icon:
                    return icon
                else:
                    return getIcon('unknown-file.png')
        except Exception:
            return QVariant(None)
        else:
            return QVariant(None)
