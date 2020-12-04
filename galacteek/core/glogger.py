import sys
import collections
from cachetools import cached
from cachetools import LRUCache
from colour import Color

from logbook import Logger, StreamHandler
from logbook import TimedRotatingFileHandler
from logbook.more import ColorizedStderrHandler
from logbook.helpers import u
from logbook.compat import redirect_warnings
from logbook.compat import redirect_logging

from galacteek.core import SingletonDecorator

mainFormatString = u(
    '[{record.time:%Y-%m-%d %H:%M:%S.%f%z}] '
    '{record.level_name}: {record.module}: {record.message}')

easyFormatString = u(
    '[{record.time: %H:%M:%S}] '
    '{record.module}: {record.message}')


@SingletonDecorator
class LogRecordStyler:
    red = Color('red')
    darkred = Color('red')
    blue = Color('blue')
    turquoise = Color('turquoise')
    green = Color('green')

    _colorCache = collections.OrderedDict()

    _defaultColor = Color('black')
    _table = {
        '*': {
            'basecolor': 'black',
        },

        # core
        'galacteek.core': {
            'basecolor': 'red'
        },
        'galacteek.core.asynclib': {
            'basecolor': 'darkred',
            'red': -0.2
        },
        'galacteek.core.profile': {
            'basecolor': 'darkred',
            'red': -0.1
        },
        'galacteek.core.tor': {
            'basecolor': 'darkred'
        },

        # crypto modules
        'galacteek.crypto': {
            'basecolor': 'brown'
        },
        'galacteek.crypto.rsa': {
            'basecolor': 'brown',
            'red': 0.2
        },
        'galacteek.crypto.ecc': {
            'basecolor': 'brown',
            'red': 0.6
        },
        'galacteek.crypto.qrcode': {
            'basecolor': 'brown',
            'red': 0.4
        },

        # ipfs modules
        'galacteek.ipfs': {
            'basecolor': 'blue'
        },
        'galacteek.ipfs.dag': {
            'basecolor': 'darkblue'
        },
        'galacteek.ipfs.ipfsops': {
            'basecolor': 'blue',
            'blue': -0.1
        },
        'galacteek.ipfs.pubsub.service': {
            'basecolor': 'blue',
            'blue': -0.2
        },
        'galacteek.ipfs.pubsub.srvs': {
            'basecolor': 'blue',
            'red': 0.5
        },
        'galacteek.ipfs.tunnel': {
            'basecolor': 'blue',
            'blue': -0.5
        },
        'galacteek.ipfs.asyncipfsd': {
            'basecolor': 'blue',
            'blue': -0.8,
            'green': 0.2
        },
        'galacteek.ipfs.p2pservices': {
            'basecolor': 'blue',
            'blue': -0.8,
            'red': 0.2
        },

        # did
        'galacteek.did': {
            'basecolor': 'darkgreen'
        },
        'galacteek.did.ipid': {
            'basecolor': 'darkgreen',
            'green': -0.3
        },

        # torrent
        'galacteek.torrent': {
            'basecolor': 'purple'
        },
        'galacteek.torrent.control': {
            'basecolor': 'purple'
        },
        'galacteek.torrent.network': {
            'basecolor': 'purple'
        },
        'galacteek.torrent.algorithms': {
            'basecolor': 'purple',
            'red': 0.2
        },

        # ui
        'galacteek.ui': {
            'basecolor': 'white',
            'blue': -0.2,
            'red': -0.1,
            'green': -0.5
        },

        # hashmarks
        'galacteek.hashmarks': {
            'basecolor': 'brown'
        },

        # dweb
        'galacteek.dweb': {
            'basecolor': 'turquoise'
        }
    }

    @cached(LRUCache(64))
    def color(self, color, r=0, g=0, b=0):
        try:
            c = Color(color)
            c.red += r
            c.green += g
            c.blue += b
        except Exception:
            return self._defaultColor
        else:
            return c

    def getStyle(self, record):
        style = self._table.get(record.module)

        def _g(st):
            cName = st.get('basecolor')
            r, g, b = st.get('red', 0), st.get('green', 0), \
                st.get('blue', 0)

            return self.color(cName, r, g, b), None

        if style:
            return _g(style)
        else:
            parent = '.'.join(record.module.split('.')[:-1])
            style = self._table.get(parent)
            if style:
                return _g(style)

            # default
            return self._defaultColor, None


class ColorizedHandler(ColorizedStderrHandler):
    dark_colors = ["black", "darkred", "darkgreen", "brown", "darkblue",
                   "purple", "teal", "lightgray"]
    light_colors = ["darkgray", "red", "green", "yellow", "blue",
                    "fuchsia", "turquoise", "white"]

    def get_color(self, record):
        if not record.module:
            return 'lightgray'
        elif record.module == 'galacteek.core.asynclib':
            return 'darkred'
        elif record.module.startswith('galacteek.core'):
            return 'red'
        elif record.module.startswith('galacteek.crypto'):
            return 'green'
        elif record.module.startswith('galacteek.ipfs'):
            return 'turquoise'
        elif record.module.startswith('galacteek.did'):
            return 'turquoise'
        elif record.module.startswith('galacteek.dweb.page'):
            return 'brown'
        elif record.module == 'galacteek.user':
            return 'fuchsia'
        elif record.module == 'galacteek.hashmarks':
            return 'brown'
        elif record.module == 'galacteek.application':
            return 'blue'
        elif record.module.startswith('galacteek.ui'):
            return 'yellow'
        else:
            return 'lightgray'


def basicConfig(outputFile=None, level='INFO',
                redirectLogging=False, colorized=False):
    if outputFile:
        handler = TimedRotatingFileHandler(outputFile,
                                           date_format='%Y-%m-%d')
    else:
        if not colorized:
            handler = StreamHandler(sys.stderr, level=level, bubble=True)
        else:
            handler = ColorizedHandler(level=level, bubble=True)
            handler.force_color()

    handler.format_string = mainFormatString
    handler.push_application()

    if redirectLogging:
        redirect_logging()
        redirect_warnings()


loggerMain = Logger('galacteek')
loggerUser = Logger('galacteek.user')
