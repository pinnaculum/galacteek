import posixpath

from galacteek.ipfs.wrappers import ipfsOp  # noqa
from galacteek.ipfs.wrappers import ipfsOpFn  # noqa


class ConnectionError(Exception):
    pass


class DaemonStartError(Exception):
    pass


def kilobytes(kb):
    return (1024 * kb)


def megabytes(mb):
    return (1024 * kilobytes(mb))


def ipfsPathJoin(*a):
    return posixpath.join(*a)


def ipfsVersionsGenerator():
    # We run 'which' on 'ipfs-{version}', the major and minor ranges
    # are minimized on purpose

    for v in reversed(range(0, 1)):
        for major in reversed(range(0, 9)):
            for minor in reversed(range(0, 25)):
                yield f'{v}.{major}.{minor}'


posixIpfsPath = posixpath
