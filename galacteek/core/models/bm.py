from PyQt5.QtCore import QModelIndex
from PyQt5.QtCore import Qt

from PyQt5.QtGui import QStandardItemModel
from PyQt5.QtGui import QStandardItem

from galacteek import database


class BMContactsModel(QStandardItemModel):
    def __init__(self, parent=None):
        super(BMContactsModel, self).__init__(parent)

    @property
    def root(self):
        return self.invisibleRootItem()

    async def update(self):
        contacts = await database.bmContactAll()

        try:
            for contact in contacts:
                idxList = self.match(
                    self.index(0, 0, QModelIndex()),
                    Qt.DisplayRole,
                    contact.bmAddress,
                    -1,
                    Qt.MatchFixedString | Qt.MatchWrap | Qt.MatchRecursive
                )

                if len(idxList) > 0:
                    # Already have this contact
                    continue

                self.root.appendRow([
                    QStandardItem(contact.bmAddress),
                    QStandardItem(contact.fullname)
                ])
        except Exception:
            pass
