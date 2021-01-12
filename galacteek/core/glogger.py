import os.path
import asyncio
import sys
import collections
import platform
import traceback
from datetime import datetime

from cachetools import cached
from cachetools import LRUCache
from colour import Color

from logbook import Logger, StreamHandler
from logbook import Handler
from logbook import TimedRotatingFileHandler
from logbook.handlers import StringFormatterHandlerMixin
from logbook.more import ColorizedStderrHandler
from logbook.helpers import u
from logbook.compat import redirect_warnings
from logbook.compat import redirect_logging
from logbook.base import _datetime_factory

from galacteek.core import SingletonDecorator
from galacteek.core import runningApp

try:
    from aiofile import AIOFile
except ImportError:
    haveAioFile = False
else:
    haveAioFile = True


mainFormatString = u(
    '[{record.time:%Y-%m-%d %H:%M:%S.%f%z}] '
    '{record.level_name}: {record.module}: {record.message}')

easyFormatString = u(
    '[{record.time: %H:%M:%S}] '
    '{record.module}: {record.message}')


loggerMain = Logger('galacteek')
loggerUser = Logger('galacteek.user')


@ SingletonDecorator
class LogRecordStyler:
    red = Color('red')
    darkred = Color('darkred')
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
        'galacteek.services.tor.process': {
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
            'basecolor': 'darkred',
            'red': -0.2
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

    @ cached(LRUCache(64))
    def color(self, color, r=0, g=0, b=0):
        try:
            c = Color(color)
            c.red += r
            c.green += g
            c.blue += b
        except ValueError as verr:
            loggerMain.warning(f'{self.__class__}: Cannot build color: {verr}')
            return self._defaultColor
        except Exception:
            return self._defaultColor
        else:
            return c

    def getStyle(self, record):
        style = self._table.get(record.module)

        def _g(st):
            cName = st.get('basecolor')
            r, g, b = st.get('red', 0), st.get('green', 0), st.get('blue', 0)

            return self.color(cName, r, g, b), None

        if style:
            return _g(style)
        else:
            if record.module:
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


class AsyncLogHandler(Handler, StringFormatterHandlerMixin):
    def __init__(self, *args, **kwargs):
        Handler.__init__(self, *args, **kwargs)
        StringFormatterHandlerMixin.__init__(self, None)

        self.app = runningApp()
        self.loop = asyncio.get_event_loop()
        self.ptask = self.loop.create_task(self._process())
        self.__queue = asyncio.Queue()

    def emit(self, record):
        if record.module and not self.app.shuttingDown:
            self.__queue.put_nowait(record)

    async def _process(self):
        while True:
            try:
                record = await self.__queue.get()
                await self.processRecord(record)
                self.__queue.task_done()
            except asyncio.CancelledError:
                return
            except Exception:
                return

    async def processRecord(self, record):
        pass


class AsyncDatedFileHandler(AsyncLogHandler):
    def __init__(self, filename,
                 mode='a', encoding='utf-8', level='debug',
                 format_string=None, date_format='%Y-%m-%d',
                 backup_count=0, filter=None, bubble=False,
                 timed_filename_for_current=True,
                 rollover_format='{basename}-{timestamp}{ext}'):
        self.format_string = format_string
        AsyncLogHandler.__init__(self)

        self.date_format = date_format
        self.backup_count = backup_count
        self.format_string = format_string
        self.encoding = encoding

        self.rollover_format = rollover_format

        self.original_filename = filename
        self.basename, self.ext = os.path.splitext(os.path.abspath(filename))
        self.timed_filename_for_current = timed_filename_for_current

        self._timestamp = self._get_timestamp(_datetime_factory())
        if self.timed_filename_for_current:
            filename = self.generate_timed_filename(self._timestamp)
        elif os.path.exists(filename):
            self._timestamp = self._get_timestamp(
                datetime.fromtimestamp(
                    os.stat(filename).st_mtime
                )
            )

        self._aio_fd = AIOFile(filename, 'w+t')
        self._aio_position = 0

    @property
    def afd(self):
        return self._aio_fd

    def _get_timestamp(self, datetime):
        return datetime.strftime(self.date_format)

    def generate_timed_filename(self, timestamp):
        """
        Produces a filename that includes a timestamp in the format supplied
        to the handler at init time.
        """
        timed_filename = self.rollover_format.format(
            basename=self.basename,
            timestamp=timestamp,
            ext=self.ext)
        return timed_filename

    async def processRecord(self, record):
        try:
            await self.afd.open()

            formatted = self.format(record) + "\n"

            await self.afd.write(
                formatted,
                offset=self._aio_position
            )
            await self.afd.fsync()

            self._aio_position += len(formatted)
        except Exception:
            traceback.print_exc()


def basicConfig(outputFile=None, level='INFO',
                redirectLogging=False, colorized=False,
                loop=None):
    if outputFile:
        if platform.system() == 'Linux' and 0:
            handler = AsyncDatedFileHandler(outputFile,
                                            date_format='%Y-%m-%d')
        else:
            handler = TimedRotatingFileHandler(outputFile,
                                               level=level,
                                               bubble=True,
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
