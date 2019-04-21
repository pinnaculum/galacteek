import sys

from logbook import Logger, StreamHandler
from logbook.helpers import u

mainFormatString = u(
    '[{record.time:%Y-%m-%d %H:%M:%S.%f%z}] '
    '{record.level_name}: {record.module}: {record.message}')

easyFormatString = u(
    '[{record.time: %H:%M:%S}] '
    '{record.module}: {record.message}')


def basicConfig(level='INFO'):
    handler = StreamHandler(sys.stderr, level=level)
    handler.format_string = mainFormatString
    handler.push_application()


loggerMain = Logger('galacteek')
loggerUser = Logger('galacteek.user')
