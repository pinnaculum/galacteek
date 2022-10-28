import html2text

from PyQt5.QtCore import QVariant
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QSize
from PyQt5.QtGui import QFont

from galacteek.core import runningApp

from galacteek.ui.helpers import getIcon

from galacteek.ui.i18n import iHashmarkInfoToolTip
from galacteek.ui.i18n import iUnknown

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
        dc = self.itemData.get('dateCreated')
        if dc:
            return dc.toPython()

    @property
    def description(self):
        return str(self.itemData.get('descr', ''))

    @property
    def mimeType(self):
        mt = self.itemData.get('mimeType')
        return str(mt) if mt is not None else iUnknown()

    def icon(self, col: int):
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

    def tooltip(self, column: int) -> str:
        if column == 0:
            iconUrl = ':/share/iconUrls/mimetypes/unknown.png'

            if self.mimeType:
                qti = getMimeIcon(self.mimeType)
                if qti:
                    iconUrl = pixmapAsBase64Url(
                        qti.pixmap(QSize(64, 64)),
                        justUrl=True
                    )

            dc = self.dateCreated

            return iHashmarkInfoToolTip(
                self.uri,
                iconUrl,
                self.title,
                self.description,
                dc.isoformat(sep=' ', timespec='seconds') if dc else ''
            )

    def data(self, column: int, role):
        if role == Qt.DisplayRole:
            if column == 0:
                return self.title[0:64]
            elif column == 1:
                return self.mimeType
        elif role == Qt.ToolTipRole:
            return self.tooltip(column)
        elif role in [SubjectUriRole, HashmarkUriRole]:
            return str(self.uri)
        elif role == Qt.FontRole:
            if column == 0:
                f = QFont('Segoe UI', 16)
                f.setBold(True)
                return f

            return QFont('Segoe UI', 14)

        return super().data(column, role)


class HashmarkSummaryItem(SparQLBaseItem):
    def displayHashmark(self):
        return '''Uri: {self.itemData["uri"]}'''

    def data(self, column: int, role):
        if role == Qt.DisplayRole and column == 0:
            return self.displayHashmark()

        return super().data(column, role)


class LDHashmarksSparQLItemModel(SparQLItemModel):
    extraDataTypes = [
        HashmarkUriRole,
        SubjectUriRole
    ]

    async def itemFromResult(self, result, parent):
        return HashmarkItem(result, parent=parent)


class LDHashmarksItemModel(LDHashmarksSparQLItemModel):
    def queryForParent(self, parent: SparQLBaseItem):
        if parent is self.rootItem:
            return self.hashmarkQuery(), {
                'uri': parent.itemData['uri']
            }

        return None, None

    def hashmarkQuery(self):
        return self.rqGet('HashmarksSearch')

    def searchHashmark(self, uri: str) -> list:
        """
        Search a hashmark by uri in the model and return
        a list of matching indexes
        """
        return self.match(
            self.createIndex(self.rootItem.row(), 0),
            SubjectUriRole,
            uri
        )

    async def searchHashmarkAsync(self, uri: str) -> list:
        return await runningApp().rexec(self.searchHashmark, uri)

    async def handleItem(self,
                         item: SparQLBaseItem,
                         parent: SparQLBaseItem):
        if isinstance(item, HashmarkItem):
            # Add a summary item (wrapping the parent item's data)

            self.insertItem(
                HashmarkSummaryItem(item.itemData, parent=item)
            )
