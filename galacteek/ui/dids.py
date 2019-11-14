from PyQt5.QtWidgets import QAction

from galacteek.did.ipid import IPIdentifier
from galacteek.did.ipid import IPService

from .helpers import getPlanetIcon


async def buildIpServicesMenu(ipid: IPIdentifier, sMenu, parent=None):
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
