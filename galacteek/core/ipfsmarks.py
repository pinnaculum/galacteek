
import collections
import os.path
import json
import time
import sys
import collections
import copy
from datetime import datetime

from async_generator import async_generator, yield_, yield_from_
import asyncio
import aiofiles

from galacteek.core.asynclib import asyncify

from PyQt5.QtCore import pyqtSignal, QUrl, QObject

class MarksEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, IPFSHashMark):
            return obj.data
        return json.JSONEncoder.default(self, obj)

marksKey = '_marks'

def rSlash(path):
    return path.rstrip('/')

class IPFSHashMark(collections.UserDict):
    @property
    def markData(self):
        return self.data[self.path]

    def addTags(self, tags):
        self.data[self.path]['tags'] += tags

    def dump(self):
        print(json.dumps(self.data, indent=4))

    @staticmethod
    def fromJson(data):
        return IPFSHashMark(data)

    @staticmethod
    def make(path, title=None, datecreated=None, share=False, tags=[],
            description='', comment='', datasize=None, cumulativesize=None,
            numlinks=None):
        if datecreated is None:
            datecreated = datetime.now().isoformat()

        path = rSlash(path)

        mData = IPFSHashMark({
            path: {
                'metadata': {
                    'title': title,
                    'description': description,
                    'datasize': datasize,
                    'cumulativesize': cumulativesize,
                    'numlinks': numlinks,
                },
                'datecreated': datecreated,
                'tscreated': int(time.time()),
                'comment': comment,
                'share': share,
                'tags': tags,
            }
        })

        mData.path = path
        return mData

class IPFSMarks(QObject):
    changed = pyqtSignal()
    markDeleted = pyqtSignal(str)
    markAdded = pyqtSignal(str, dict)

    def __init__(self, path, parent=None, autosave=True):
        super().__init__(parent)

        self._path = path
        self._autosave = autosave
        self._marks = self.load()
        self.changed.connect(self.onChanged)
        self.lastsaved = time.time()
        self.changed.emit()

    @property
    def path(self):
        return self._path

    @property
    def autosave(self):
        return self._autosave

    @property
    def asyncQ(self):
        """ Async query """
        return _AsyncMarksQuery(self)

    @property
    def _root(self):
        return self._marks

    @property
    def _rootMarks(self):
        return self._root['ipfsmarks']

    @property
    def _rootCategories(self):
        return self._rootMarks['categories']

    @property
    def _rootFeeds(self):
        return self._root['feeds']

    def load(self):
        try:
            marks = json.load(open(self.path, 'rt'))
            return marks
        except Exception as e:
            marks = collections.OrderedDict()

        if not 'ipfsmarks' in marks:
            marks['ipfsmarks'] = {}
            marks['ipfsmarks']['categories'] = {}
        if not 'feeds' in marks:
            marks['feeds'] = {}

        return marks

    def onChanged(self):
        if self.autosave is True:
            self.save()

    def save(self):
        """ Save synchronously """
        with open(self.path, 'w+t') as fd:
            self.serialize(fd)
            self.lastsaved = time.time()

    async def saveAsync(self):
        async with aiofiles.open(self.path, 'w+t') as fd:
            await fd.write(json.dumps(self._root, indent=4, cls=MarksEncoder))
            self.lastsaved = time.time()

    def hasCategory(self, category, parent=None):
        if parent is None:
            parent = self._rootCategories
        return category in parent

    def enterCategory(self, section, create=False):
        comps = section.lstrip('/').rstrip('/').split('/')
        return self.walk(comps, create=create)

    def walk(self, path, create=True):
        # Walk to a category and create intermediary parents if create
        # is True. path is a list of category components 
        # e.g ['general', 'news'] for category path /general/news
        def _walk(path, parent=None):
            for p in path:
                if p.startswith('_'):
                    return
                if p in parent.keys():
                    parent = parent[p]
                elif p not in parent.keys() and create is True:
                    self.addCategory(p, parent=parent)
                    parent = parent[p]
                else:
                    return
            return parent
        return _walk(path, parent=self._rootCategories)

    def getCategories(self):
        def _list(path, parent=None):
            for p in parent.keys():
                if p.startswith('_'):
                    continue

                fullPath = path + [p]
                yield '/'.join(fullPath)
                yield from  _list(fullPath, parent=parent[p])

        return list(_list([], parent=self._rootCategories))

    def addCategory(self, category, parent=None):
        if parent is None:
            parent = self._rootCategories

        if len(category) > 256:
            return None

        if not self.hasCategory(category, parent=parent):
            parent[category] = {
                marksKey: {}
            }
            self.changed.emit()
            return parent[category]

    def getCategoryMarks(self, category, usecopy=False):
        sec = self.enterCategory(category)
        if sec:
            if usecopy:
                return copy.copy(sec[marksKey])
            else:
                return sec[marksKey]

    def getAll(self, share=False):
        cats = self.getCategories()
        _all = {}
        for cat in cats:
            catMarks = self.getCategoryMarks(cat)
            for mpath, mark in catMarks.items():
                if mark['share'] == share:
                    _all[mpath] = mark
        return _all

    def search(self, bpath, category=None, tags=[], delete=False):
        path = rSlash(bpath)
        categories = self.getCategories()

        for cat in categories:
            if category and cat != category:
                continue

            marks = self.getCategoryMarks(cat)
            if not marks:
                continue

            if path in marks.keys():
                if delete is True:
                    del marks[path]
                    self.markDeleted.emit(path)
                    self.changed.emit()
                    return True

                tagsOk = True
                m = marks[path]
                for stag in tags:
                    if stag not in m['tags']:
                        tagsOk = False

                if tagsOk:
                    return (path, marks[path])

    def insertMark(self, mark, category):
        # Insert a mark in given category, checking of already existing mark
        # is left to the caller
        sec = self.enterCategory(category, create=True)
        if not sec:
            return False

        # Handle IPFSHashMark or tuple
        if isinstance(mark, IPFSHashMark):
            sec[marksKey].update(mark)
            self.markAdded.emit(mark.path, mark.markData)
        else:
            try:
                mPath, mData = mark
                sec[marksKey][mPath] = mData
                self.markAdded.emit(mPath, mData)
            except Exception as e:
                return False

        self.changed.emit()
        return True

    def add(self, bpath, title=None, category='general', share=False, tags=[]):
        if not bpath:
            return None

        path = rSlash(bpath)

        sec = self.enterCategory(category, create=True)

        if not sec:
            return False

        if self.search(path):
            # We already have stored a mark with this path
            return False

        mark = IPFSHashMark.make(path,
            title=title,
            datecreated=datetime.now().isoformat(),
            share=share,
            tags=tags,
        )

        sec[marksKey].update(mark)
        self.changed.emit()
        self.markAdded.emit(path, mark.markData)

        return True

    def delete(self, path):
        return self.search(path, delete=True)

    def merge(self, oMarks):
        for cat in oMarks.getCategories():
            marks = oMarks.getCategoryMarks(cat)
            for mark in marks.items():
                r = self.insertMark(mark, cat)

    def follow(self, ipnsp, name, active=True, maxentries=4096,
            resolveevery=3600, share=False, autoPin=False):
        if ipnsp is None:
            return

        feedsSec = self._rootFeeds
        ipnsp = rSlash(ipnsp)

        if ipnsp in feedsSec:
            return
        feedsSec[ipnsp] = {
            'name': name,
            'active': active,
            'maxentries': maxentries,
            'resolvepolicy': 'auto',
            'resolveevery': resolveevery,
            'resolvedlast': None,
            'share': share,
            'autopin': autoPin,
            marksKey: {},
        }
        self.changed.emit()
        return feedsSec[ipnsp]

    def feedAddMark(self, ipnsp, mark):
        feeds = self._rootFeeds
        if not ipnsp in feeds:
            return False
        sec = feeds[ipnsp][marksKey]
        if mark.path in sec:
            return False

        feeds[ipnsp][marksKey].update(mark)
        self.changed.emit()
        return True

    def getFeeds(self):
        return list(self._rootFeeds.items())

    def getFeedMarks(self, path):
        feeds = self.getFeeds()
        for fPath, fData in feeds:
            if fPath == path:
                return fData[marksKey]

    def serialize(self, fd):
        return json.dump(self._root, fd, indent=4, cls=MarksEncoder)

    def dump(self):
        print(self.serialize(sys.stdout))

    def norm(self, path):
        return path.rstrip('/')

class _AsyncMarksQuery:
    """
    Class designed to make operations on the marks tree asynchronously.
    """
    def __init__(self, marks):
        self.m = marks

    async def search(self, bpath, category=None, tags=[], delete=False):
        path = rSlash(bpath)

        getCategories = await self.getCategories()

        for cat in getCategories:
            await asyncio.sleep(0)
            if category and cat != category:
                continue

            marks = await self.getCategoryMarks(cat)
            if path in marks:
                if delete is True:
                    del marks[path]
                    self.changed.emit()
                    return True

                tagsOk = True
                m = marks[path]
                for stag in tags:
                    if stag not in m['tags']:
                        tagsOk = False

                if tagsOk:
                    return marks[path]

    async def add(self, bpath, title=None, category='general', share=False,
            tags=[]):
        if not bpath:
            return None

        path = rSlash(bpath)
        sec =  self.m.enterCategory(category, create=True)
        if not sec:
            return False

        if await self.search(path):
            # We have already stored a mark with this path
            return False

        mark = IPFSHashMark.make(path,
            title=title,
            datecreated=datetime.now().isoformat(),
            share=share,
            tags=tags,
        )

        sec[marksKey].update(mark)
        self.m.changed.emit()

        return True

    async def walkAsync(self, path, create=True):
        async def _w(path, parent=None):
            for p in path:
                await asyncio.sleep(0)
                if p.startswith('_'):
                    return
                if p in parent.keys():
                    parent = parent[p]
                elif p not in parent.keys() and create is True:
                    self.addCategory(p, parent=parent)
                    parent = parent[p]
                else:
                    return
            return parent

        return await _w(path, parent=self.m._rootCategories)

    async def getCategories(self):
        @async_generator
        async def _list(path, parent=None):
            for p in parent.keys():
                await asyncio.sleep(0)
                if p.startswith('_'):
                    continue

                fullPath = path + [p]
                await yield_( '/'.join(fullPath) )
                await yield_from_( _list(path + [p], parent=parent[p]) )

        cats = []
        async for v in _list([], parent=self.m._rootCategories):
            cats.append(v)
        return cats

    async def getCategoryMarks(self, category):
        sec = self.m.enterCategory(category)
        if sec:
            return copy.copy(sec[marksKey])

    async def enterCategory(self, section, create=False):
        comps = section.lstrip('/').rstrip('/').split('/')
        return await self.walkAsync(comps, create=create)
