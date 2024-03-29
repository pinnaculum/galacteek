from typing import Union


class StatInfo:
    # Object stat info
    def __init__(self, statInfo: Union[object, dict]):
        if isinstance(statInfo, StatInfo):
            self.stat = dict(statInfo.stat)
        else:
            self.stat = statInfo

    @property
    def valid(self):
        # :-/
        return isinstance(self.stat, dict) and \
            'DataSize' in self.stat and \
            'CumulativeSize' in self.stat and \
            'NumLinks' in self.stat and \
            'BlockSize' in self.stat and \
            'LinksSize' in self.stat

    @property
    def cid(self):
        return self.stat.get('Hash')

    @property
    def totalSize(self):
        return self.stat.get('CumulativeSize')

    @property
    def dataSize(self):
        return self.stat.get('DataSize')

    @property
    def numLinks(self):
        return self.stat.get('NumLinks')

    @property
    def blockSize(self):
        return self.stat.get('BlockSize')

    @property
    def linksSize(self):
        return self.stat.get('LinksSize')

    def dataLargerThan(self, size):
        if self.valid:
            return self.dataSize > size

    def dataSmallerThan(self, size):
        if self.valid:
            return self.dataSize < size


class UnixFsStatInfo:
    """
    Files (unixfs) stat info
    """

    def __init__(self, statInfo: Union[object, dict]):
        if isinstance(statInfo, UnixFsStatInfo):
            self.stat = dict(statInfo.stat)
        else:
            self.stat = statInfo

    @property
    def valid(self):
        return isinstance(self.stat, dict) and \
            'CumulativeSize' in self.stat and \
            'Size' in self.stat

    @property
    def cid(self):
        return self.stat.get('Hash')

    @property
    def totalSize(self):
        return self.stat.get('CumulativeSize')

    @property
    def type(self):
        return self.stat.get('Type')

    @property
    def linksSize(self):
        return self.stat.get('LinksSize')

    def dataLargerThan(self, size):
        if self.valid:
            return self.dataSize > size

    def dataSmallerThan(self, size):
        if self.valid:
            return self.dataSize < size
