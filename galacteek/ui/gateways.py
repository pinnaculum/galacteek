import functools
from yarl import URL
from cachetools import TTLCache

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QMenu

from galacteek import ensure
from galacteek import partialEnsure
from galacteek import AsyncSignal
from galacteek.config.cmods import ipfs as cmod_ipfs
from galacteek.core import SingletonDecorator

from galacteek.ipfs.fetch import checkGateway

from .helpers import getIcon
from .i18n import iCopySpGwUrlToClipboard


@SingletonDecorator
class GatewaysChecker:
    """
    IPFS HTTP gateways availability checker

    TODO: move to galacteek.ipfs.fetch
    """

    _cache: TTLCache = TTLCache(16, 240)

    checkResult = AsyncSignal(URL, bool, float)

    async def check(self, gwUrl: URL) -> None:
        """
        Check if a gateway if available by running a GET request
        with checkGateway and cache the result.

        Emits the checkResult async signal, so that all menus which
        want infos about gateways will get the same infos.
        """

        _key = str(gwUrl)
        cached = self._cache.get(_key)

        if cached:
            # Emit cached result
            await self.checkResult.emit(gwUrl, cached[0], cached[1])

            return

        result, resptime = await checkGateway(gwUrl)

        if result:
            self._cache[_key] = result, resptime

        await self.checkResult.emit(gwUrl, result, resptime if result else 0)


async def onCheckResult(menu,
                        gwUrl: URL,
                        avail: bool,
                        rtime: float) -> None:
    """
    Called when a gateway check result is emitted by the
    gateways checker class.
    """

    for action in menu.actions():
        data = action.data()

        if isinstance(data, URL) and gwUrl == data:
            if avail:
                action.setIcon(getIcon('ipfs-cube-64.png'))
                action.setText(f'{gwUrl.host} ({rtime:.2f} secs)')
            else:
                # change icon
                action.setIcon(getIcon('cancel.png'))
                action.setText(f'{gwUrl.host} (unavail)')

            break


def onMenuAboutToShow(menu: QMenu):
    """
    Called when a gateways list menu is about to be shown.

    For each gateway, we run the gateway checker.
    """

    gwc = GatewaysChecker()

    for action in menu.actions():
        # No need to check data(), it's always a URL
        ensure(gwc.check(action.data()))


def gatewaysMenu(signal: pyqtSignal,
                 parent=None,
                 runCheck: bool = False,
                 menuText: str = None):
    menu = QMenu(menuText if menuText else iCopySpGwUrlToClipboard(),
                 parent=parent)
    menu.setIcon(getIcon('clipboard.png'))
    menu.setToolTipsVisible(True)

    # Bind to the gw checker's checkResult signal
    gwc = GatewaysChecker()
    gwc.checkResult.connectTo(partialEnsure(onCheckResult, menu))

    try:
        gateways = cmod_ipfs.ipfsHttpGatewaysAvailable()
    except Exception:
        # TODO: Add some defaults here
        gateways = []

    for gw in gateways:
        url = URL(gw)

        action = menu.addAction(
            getIcon('ipfs-cube-64.png' if not runCheck else
                    'ipfs-logo-128-black.png'),
            url.host,
            functools.partial(
                signal.emit,
                url
            ))

        action.setData(url)

    if runCheck:
        # Bind aboutToShow to run the gw checks when the menu is shown
        menu.aboutToShow.connect(functools.partial(onMenuAboutToShow, menu))

    return menu
