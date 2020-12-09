import collections
import json
import sys
from functools import reduce
from pathlib import Path

from PyQt5.QtCore import pyqtSignal, QObject


class QJSONObj(QObject):
    changed = pyqtSignal()

    def __init__(self, data=None, **kw):
        super().__init__()

        self.__dict__.update(kw)
        self._load(data)
        self.changed.connect(self.onChanged)
        self.changed.emit()

    @property
    def root(self):
        return self._root

    def _load(self, data):
        self._root = data if data else self._init()

    def set(self, data):
        self._root = data

    def prepare(self, root):
        pass

    def save(self):
        pass

    def _init(self):
        root = {}
        self.prepare(root)
        return root

    def onChanged(self):
        self.save()

    def __str__(self):
        return json.dumps(self.root)

    def serialize(self, fd):
        return json.dump(self.root, fd, indent=4)

    def dump(self):
        self.serialize(sys.stdout)


class QJSONFile(QJSONObj):
    def __init__(self, path, **kw):
        self._path = path

        super(QJSONFile, self).__init__(**kw)

    def _init(self):
        try:
            root = json.load(open(self.path, 'rt'))
        except Exception:
            root = collections.OrderedDict()
        self.prepare(root)

        return root

    @property
    def path(self):
        return self._path

    def save(self):
        with open(self.path, 'w+t') as fd:
            self.serialize(fd)


class DotJSON(dict):
    """
    Based on edict, described here:

    https://gist.github.com/markhu/fbbab71359af00e527d0
    """

    __delattr__ = dict.__delitem__

    def __init__(self, data):
        if isinstance(data, str):
            data = json.loads(data)
        else:
            data = data

        for name, value in data.items():
            setattr(self, name, self._wrap(value))

    def _traverse(self, obj, attr):
        attrd = attr.replace('__', '-')
        if self._is_indexable(obj):
            try:
                return obj[int(attrd)]
            except:
                return None
        elif isinstance(obj, dict):
            return obj.get(attrd, None)
        else:
            return attrd

    def __getattr__(self, attr):
        if '.' in attr:
            attrVal = attr.split('.').replace('__', '-')
            return reduce(self._traverse, attrVal, self)
        return self.get(attr, None)

    def __setattr__(self, attr, value):
        attrd = attr.replace('__', '-')
        dict.__setitem__(self, attrd, value)

    def _wrap(self, value):
        if self._is_indexable(value):
            # (!) recursive (!)
            return type(value)([self._wrap(v) for v in value])
        elif isinstance(value, dict):
            return DotJSON(value)
        else:
            return value

    @staticmethod
    def _is_indexable(obj):
        return isinstance(obj, (tuple, list, set, frozenset))

    def write(self, fd):
        fd.write(json.dumps(self))
        fd.flush()

    async def writeAsync(self, path: Path):
        from galacteek.core.asynclib import asyncWriteFile

        await asyncWriteFile(str(path), json.dumps(self), mode='w+t')
