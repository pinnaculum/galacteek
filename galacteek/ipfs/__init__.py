from galacteek.ipfs.wrappers import ipfsOp  # noqa
from galacteek.ipfs.wrappers import ipfsOpFn  # noqa


def kilobytes(kb):
    return (1024 * kb)


def megabytes(mb):
    return (1024 * kilobytes(mb))
