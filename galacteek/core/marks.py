
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
            json.dump(self._marks, fd)

    def empty(self, category):
        if category in self._marks['bookmarks']:
            self._marks['bookmarks'][category] = []
            self.changed.emit()

    def hasCategory(self, category):
        return category in self._marks['bookmarks']

    def addCategory(self, category):
        self._marks['bookmarks'][category] = []
        self.changed.emit()

    def getAll(self):
        return self._marks['bookmarks']

    def getForCategory(self, category='main'):
        return self._marks['bookmarks'].get(category, [])

    def search(self, url=None, category=None):
        for cat, marks in self._marks['bookmarks'].items():
            if category and cat != category:
                continue
            for mark in marks:
                if url and mark['url'] == url:
                    return mark

    def add(self, url, title=None, category='main'):
        if not self.hasCategory(category):
            self.addCategory(category)

        if self.search(url=url):
            return False

        sec = self._marks['bookmarks'][category]

        sec.append({
            'url': url,
            'title': title,
            'created': int(time.time())
            })

        self.changed.emit()
        return True

    def dump(self):
        print(json.dumps(self._marks, indent=4))
