import html2text

from PyQt5.QtCore import QVariant
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QSize
from PyQt5.QtGui import QFont

from galacteek.ui.helpers import getIcon

from galacteek.ui.i18n import iHashmarkInfoToolTip
from galacteek.ui.helpers import getMimeIcon
from galacteek.ui.helpers import pixmapAsBase64Url

from . import SparQLListModel
from . import SparQLItemModel
from . import SparQLBaseItem
from . import SubjectUriRole


HashmarkUriRole = Qt.UserRole + 1

h2text = html2text.HTML2Text()
h2text.emphasis_mark = ''


def h2t(text):
    return h2text.handle(text).replace('\n', '').strip()


class LDHashmarksSparQLListModel(SparQLListModel):
    def data(self, QModelIndex, role=None):
        row = QModelIndex.row()

        try:
            item = self._results[row]
        except (KeyError, IndexError):
            return QVariant(None)

        try:
            if role == Qt.DisplayRole:
                return h2t(str(item['title'][0:64]))

            elif role == SubjectUriRole:
                return str(item['uri'])
            elif role == HashmarkUriRole:
                return str(item['uri'])
            elif role == Qt.ToolTipRole:
                return h2t(str(item['descr']))
            elif role == Qt.FontRole:
                return QFont('Segoe UI', 16)

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


class HashmarkItem(SparQLBaseItem):
    @property
    def uri(self):
        # URIRef
        return str(self.itemData.get('uri'))

    @property
    def title(self):
        return str(self.itemData.get('title'))

    @property
    def dateCreated(self):
        return self.itemData.get('dateCreated').toPython()

    @property
    def description(self):
        return str(self.itemData.get('descr', ''))

    @property
    def mimeType(self):
        return str(self.itemData.get('mimeType'))

    def icon(self, col):
        if col == 0:
            thumbnailUrl = self.itemData['thumbnailUrl']
            if thumbnailUrl:
                # todo
                pass

            mType = str(self.itemData['mimeType'])

            if not mType:
                return None

            icon = getMimeIcon(mType)

            if icon:
                return icon
            else:
                return getIcon('unknown-file.png')

    def tooltip(self, column: int):
        if column == 0:
            icon = ':/share/icons/mimetypes/unknown.png'

            if self.mimeType:
                qti = getMimeIcon(self.mimeType)
                if qti:
                    icon = pixmapAsBase64Url(
                        qti.pixmap(QSize(64, 64)),
                        justUrl=True
                    )

            return iHashmarkInfoToolTip(
                self.uri,
                icon,
                self.title,
                self.description,
                self.dateCreated.isoformat(sep=' ', timespec='seconds')
            )

    def data(self, column: int, role):
        if role == Qt.DisplayRole:
            if column == 0:
                return self.title[0:64]
            elif column == 1:
                return self.mimeType
        elif role in [SubjectUriRole, HashmarkUriRole]:
            return str(self.uri)
        elif role == Qt.FontRole:
            if column == 0:
                f = QFont('Segoe UI', 16)
                f.setBold(True)
                return f

            return QFont('Segoe UI', 14)

        return super().data(column, role)


class LDHashmarksSparQLItemModel(SparQLItemModel):
    extraDataTypes = [
        HashmarkUriRole,
        SubjectUriRole
    ]

    async def itemFromResult(self, result, parent):
        return HashmarkItem(result, parent=parent)
