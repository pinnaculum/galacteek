
import collections
import os.path
import json
import time
import pprint
import sys

from PyQt5.QtCore import pyqtSignal, QUrl, QObject
from PyQt5.QtCore import (QCoreApplication, QStandardPaths)

class Bookmarks(QObject):
    changed = pyqtSignal()

    def __init__(self, path, parent=None):
        super().__init__(parent)

        if path is None:
            dir = QStandardPaths.writableLocation(QStandardPaths.DataLocation)
            path = os.path.join(dir, 'bookmarks.json')

        self.path = path
        self._marks = self.load()
        self.changed.connect(self.onChanged)

    def getPath(self):
        return self.path

    def root(self):
        return self._marks['bookmarks']

    def load(self):
        try:
            marks = json.load(open(self.path, 'rt'))
            return marks
        except:
            print('Error loading bookmarks', file=sys.stderr)

        marks = collections.OrderedDict()
        marks['bookmarks'] = {}
        return marks

    def onChanged(self):
        with open(self.getPath(), 'w+t') as fd:
            json.dump(self._marks, fd, indent=4)

    def empty(self, category):
        if category in self.root():
            self.root()[category] = []
            self.changed.emit()

    def hasCategory(self, category):
        return category in self.root()

    def getCategories(self):
        return self.root().keys()

    def addCategory(self, category):
        self.root()[category] = []
        self.changed.emit()

    def getAll(self):
        return self.root()

    def getForCategory(self, category='main'):
        return self.root().get(category, [])

    def search(self, path=None, category=None):
        for cat, marks in self.root().items():
            if category and cat != category:
                continue
            for mark in marks:
                if path and mark['path'] == path:
                    return mark

    def add(self, path, title=None, category='main',
            share=False):
        if not self.hasCategory(category):
            self.addCategory(category)

        if self.search(path=path):
            return False

        sec = self.root()[category]

        sec.append({
            'path': path,
            'title': title,
            'created': int(time.time()),
            'share': share
            })

        self.changed.emit()
        return True

    def dump(self):
        print(json.dumps(self._marks, indent=4))
