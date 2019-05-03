from galacteek.ipfs.wrappers import ipfsOp  # noqa
from galacteek.ipfs.wrappers import ipfsOpFn  # noqa


def kilobytes(kb):
    return (1024 * kb)


def megabytes(mb):
    return (1024 * kilobytes(mb))


class StatInfo:
    def __init__(self, statInfo):
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
