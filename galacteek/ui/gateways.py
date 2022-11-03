import functools
from yarl import URL

from PyQt5.QtWidgets import QMenu

from galacteek.config.cmods import ipfs as cmod_ipfs

from .helpers import getIcon
from .i18n import iCopySpecificGwUrlToClipboard


def onGatewayAction(signal,
                    gwUrl: str, *args):
    signal.emit(URL(str(gwUrl)))


def gatewaysMenu(signal, parent=None):
    menu = QMenu(iCopySpecificGwUrlToClipboard(), parent=parent)
    menu.setIcon(getIcon('clipboard.png'))

    try:
        gateways = cmod_ipfs.ipfsHttpGatewaysAvailable()
    except Exception:
        # TODO: Add some defaults here
        gateways = []

    for gw in gateways:
        action = menu.addAction(
            getIcon('ipfs-cube-64.png'),
            gw,
            functools.partial(
                onGatewayAction,
                signal,
                gw
            ))

        action.setData(URL(str(gw)))

    return menu
