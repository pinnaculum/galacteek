from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QMenu

from galacteek.did.ipid import IPIdentifier
from galacteek.did.ipid import IPService

from .helpers import getIcon
from .helpers import getPlanetIcon
from .i18n import iIPServices


async def buildIpServicesMenu(ipid: IPIdentifier, parent=None):
    # Services menu
    sMenu = QMenu(iIPServices(), parent)
    sMenu.setToolTipsVisible(True)
    sMenu.setIcon(getIcon('ipservice.png'))

    services = await ipid.getServices()

    if not services:
        return sMenu

    for srvNode in services:
        service = IPService(srvNode)

        action = QAction(
            getPlanetIcon('uranus.png'),
            str(service),
            sMenu)
        action.setData(service)
        action.setToolTip(service.id)
        sMenu.addAction(action)
        sMenu.addSeparator()

    return sMenu
