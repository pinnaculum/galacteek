from PyQt5.QtCore import QVariant
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from . import SparQLListModel
from . import SubjectUriRole


class TagsSparQLModel(SparQLListModel):
    """
    Tags model
    """

    rq = 'TagsSearch'

    def tagNames(self):
        for ri in range(0, self.rowCount()):
            yield self.data(
                self.createIndex(ri, 0),
                role=Qt.DisplayRole
            )

    def tagUris(self):
        for ri in range(0, self.rowCount()):
            yield self.data(
                self.createIndex(ri, 0),
                role=SubjectUriRole
            )

    def data(self, index, role=None):
        try:
            item = self._results[index.row()]

            if role == Qt.DisplayRole:
                return str(item['tagName'])
            elif role == SubjectUriRole:
                return item['uri']
            elif role == Qt.ToolTipRole:
                return str(item['uri'])
            elif role == Qt.FontRole:
                return QFont('Montserrat', 16)
        except Exception:
            return QVariant(None)


class TagInfosSparQLModel(SparQLListModel):
    """
    Informations about a tag
    """

    def data(self, index, role=None):
        try:
            item = self._results[index.row()]

            if role == Qt.DisplayRole:
                return str(item['tagName'])
            elif role == Qt.ToolTipRole:
                return str(item['uri'])
            elif role == Qt.FontRole:
                return QFont('Montserrat', 18)
        except Exception:
            return QVariant(None)
