from async_generator import async_generator, yield_, yield_from_
import asyncio

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

""" Asynchronous equivalents for when calling from coroutines """

@async_generator
async def modelWalkAsync(model, parent=QModelIndex(), search=None,
        columns=None, delete=False, dump=False,
        maxdepth=0, depth=0):
    for row in range(0, model.rowCount(parent)):
        await asyncio.sleep(0)

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
                    await yield_(index)
        await asyncio.sleep(0)
        if model.hasChildren(index0):
            if maxdepth == 0 or (maxdepth > depth):
                await yield_from_( modelWalkAsync(model, parent=index0,
                    search=search, columns=columns, delete=delete,
                    dump=dump, maxdepth=maxdepth, depth=depth) )
                depth += 1

async def modelSearchAsync(model, parent=QModelIndex(), search=None,
        columns=None, delete=False, maxdepth=0, depth=0):
    items = []
    async for v in modelWalkAsync(model, parent=parent, columns=columns,
            search=search, delete=delete, maxdepth=maxdepth, depth=depth):
        items.append(v)
    return items

async def modelDeleteAsync(model, search):
    return await modelSearchAsync(model, search=search, delete=True)

class UneditableItem(QStandardItem):
    def __init__(self, text, icon=None):
        if icon:
            super().__init__(icon, text)
        else:
            super().__init__(text)
        self.setEditable(False)
