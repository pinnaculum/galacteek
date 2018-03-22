
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import QModelIndex

""" Helper functions to operate on QT item models """

def modelWalk(model, parent=QModelIndex(), search=None,
        columns=None, delete=False, dump=False):
    # Walk the tree baby!

    for row in range(0, model.rowCount(parent)):
        index0 = model.index(row, 0, parent)
        if columns:
            cols = columns
        else:
            cols = [c for c in range(0, model.columnCount(parent))]
        for col in cols:
            index = model.index(row, col, parent)
            if not index:
                continue
            data = model.data(index)
            if search:
                if search == data:
                    if delete == True:
                        model.removeRow(row, parent)
                        model.submit()
                    yield index
        if model.hasChildren(index0):
            yield from modelWalk(model, parent=index0,
                    search=search, columns=columns, delete=delete,
                    dump=dump)

def modelSearch(model, parent=QModelIndex(), search=None,
        columns=None, delete=False):
    return list(modelWalk(model, parent=parent, columns=columns,
        search=search, delete=delete))

def modelDelete(model, search):
    return list(modelSearch(model, search=search, delete=True))
