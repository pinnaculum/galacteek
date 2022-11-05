from PyQt5.QtCore import QVariant
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from . import SparQLListModel
from . import SubjectUriRole


TagNameRole = Qt.UserRole + 4
TagDisplayNameRole = Qt.UserRole + 5
TagWatchedRole = Qt.UserRole + 6
TagMeaningUrlsRole = Qt.UserRole + 7
TagAbstractRole = Qt.UserRole + 8


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

    def tagsDetails(self):
        for ri in range(0, self.rowCount()):
            idx = self.createIndex(ri, 0)
            yield self.data(
                idx,
                role=SubjectUriRole
            ), self.data(
                idx,
                role=TagNameRole
            ), self.data(
                idx,
                role=TagDisplayNameRole
            )

    def abstractSummarize(self, abstract: str, lines: int = 10):
        return '\n'.join(abstract.split('.')[0:lines])

    def data(self, index, role=None):
        try:
            item = self.resultGet(index)

            if role == Qt.DisplayRole:
                dn = item.get('tagDisplayName')
                if dn:
                    return str(dn)

                return str(item['tagName'])
            elif role == TagNameRole:
                var = item['tagName']
                if var:
                    return str(var)
            elif role == TagDisplayNameRole:
                var = item['tagDisplayName']
                if var:
                    return str(var)
            elif role == TagMeaningUrlsRole:
                var = item.get('meanings')
                if var:
                    return str(var)
                return ''
            elif role == TagAbstractRole:
                return str(item.get('tagAbstract', ''))
            elif role == SubjectUriRole:
                return item['uri']
            elif role == Qt.ToolTipRole:
                abstract = item.get('tagAbstract')
                if abstract:
                    return self.abstractSummarize(str(abstract))

                return str(item['uri'])
            elif role == Qt.FontRole:
                return QFont('Montserrat', 14)
        except Exception:
            return QVariant(None)


class TagsPreferencesModel(SparQLListModel):
    """
    Tags preferences model
    """

    rq = 'TagsManager'

    def tagsWatching(self):
        yield from self.rgen(
            Qt.DisplayRole,
            TagDisplayNameRole,
            TagWatchedRole
        )

    def data(self, index, role=None):
        item = self.resultGet(index)

        if role == Qt.DisplayRole:
            return str(item['tagName'])
        elif role == SubjectUriRole:
            return str(item['uri'])
        elif role == TagWatchedRole:
            return item['tagWatched']
        elif role == TagDisplayNameRole:
            var = item.get('tagDisplayName')
            if var:
                return str(var)


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
                return QFont('Montserrat', 14)
            else:
                return super().data(index, role)
        except Exception:
            return QVariant(None)
