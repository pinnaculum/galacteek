import posixpath

from galacteek.ipfs.wrappers import ipfsOp  # noqa
from galacteek.ipfs.wrappers import ipfsOpFn  # noqa


class ConnectionError(Exception):
    pass


def kilobytes(kb):
    return (1024 * kb)


def megabytes(mb):
    return (1024 * kilobytes(mb))


def ipfsPathJoin(*a):
    return posixpath.join(*a)


posixIpfsPath = posixpath
