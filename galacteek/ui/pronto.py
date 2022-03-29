from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QMenu

from galacteek import services

from .i18n import iProntoGraphs
from .helpers import getIcon


def buildProntoGraphsMenu():
    pronto = services.getByDotName('ld.pronto')

    icon = getIcon('linked-data/chain-link.png')
    menu = QMenu(iProntoGraphs())
    menu.setIcon(icon)

    for graphUri in pronto.graphsUrisStrings:
        action = QAction(
            icon,
            graphUri,
            menu
        )
        action.setData(graphUri)

        menu.addAction(action)
        menu.addSeparator()

    return menu
