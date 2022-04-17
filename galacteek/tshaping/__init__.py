from galacteek.config import cGet
from galacteek.tshaping.ttroll import TrafficTrollShaper

import platform

try:
    import traffictroll  # noqa
except ImportError:
    haveTroll = False
else:
    haveTroll = True  # ^_^


def platformTrafficShaper():
    ttEnabled = cGet('enabled', mod=f'{__name__}.ttroll')

    if haveTroll and platform.system() == 'Linux' and ttEnabled:
        return TrafficTrollShaper(debug=True)
