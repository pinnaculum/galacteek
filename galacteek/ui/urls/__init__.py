from typing import Union

from colorhash import ColorHash

from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QColor

from galacteek import log
from galacteek.ipfs import ipfsOpFn
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ipfs.cidhelpers import getCID
from galacteek.browser.schemes import SCHEME_IPFS
from galacteek.browser.schemes import SCHEME_IPNS
from galacteek.browser.schemes import SCHEME_DWEB


def colorize(data: Union[str, bytes]):
    """
    Use colorhash.ColorHash to convert data to a QColor
    """
    ch = ColorHash(data)

    return QColor.fromRgb(
        ch.rgb[0],
        ch.rgb[1],
        ch.rgb[2]
    )


@ipfsOpFn
async def urlColor(ipfsop, arg: Union[QUrl, IPFSPath, str]):
    """
    Compute a QColor for any type of URL
    """

    if isinstance(arg, QUrl):
        if arg.scheme() in [SCHEME_IPFS, SCHEME_IPNS, SCHEME_DWEB]:
            path = IPFSPath(arg.toString(), autoCidConv=True)
        else:
            return colorize(arg.toString())
    elif isinstance(arg, str):
        path = IPFSPath(arg, autoCidConv=True)
    elif isinstance(arg, IPFSPath):
        path = arg
    else:
        return None

    try:
        assert path.valid

        cid = getCID(await path.resolve(ipfsop))
        if not cid:
            return None

        return colorize(cid.multihash)
    except Exception as err:
        log.debug(f'{path}: could not calculate color: {err}')

    return None
