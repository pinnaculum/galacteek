import sys

from logbook import Logger, StreamHandler
from logbook.compat import redirect_logging
from logbook.helpers import u

mainFormatString = u(
    '[{record.time:%Y-%m-%d %H:%M:%S.%f%z}] '
    '{record.level_name}: {record.channel}/{record.module}: {record.message}')

def basicConfig(level='INFO'):
    handler = StreamHandler(sys.stderr, level=level)
    handler.format_string = mainFormatString
    handler.push_application()

loggerMain = Logger('galacteek')
