from math import floor, log
from typing import List, TypeVar, Sequence


T = TypeVar('T', Sequence, memoryview)


def grouper(arr: T, group_size: int) -> List[T]:
    # Yield successive n-sized chunks from l.

    return [arr[i:i + group_size] for i in range(0, len(arr), group_size)]


UNIT_BASE = 2 ** 10
UNIT_PREFIXES = 'KMG'


def humanize_size(size: float) -> str:
    if not size:
        return '0'
    if size < UNIT_BASE:
        return '{:.0f} bytes'.format(size)
    unit = floor(log(size, UNIT_BASE))
    unit_name = UNIT_PREFIXES[min(unit, len(UNIT_PREFIXES)) - 1] + 'iB'
    return '{:.1f} {}'.format(size / UNIT_BASE ** unit, unit_name)


def humanize_speed(speed: int) -> str:
    return humanize_size(speed) + '/s'


SECONDS_PER_MINUTE = 60
MINUTES_PER_HOUR = 60


def humanize_time(total_seconds: int) -> str:
    if total_seconds < SECONDS_PER_MINUTE:
        return 'less than a minute'
    total_minutes = round(total_seconds / SECONDS_PER_MINUTE)

    hours = total_minutes // MINUTES_PER_HOUR
    minutes = total_minutes % MINUTES_PER_HOUR
    result = '{} min'.format(minutes)
    if hours:
        result = '{} h '.format(hours) + result
    return result


def floor_to(x: float, ndigits: int) -> float:
    scale = 10 ** ndigits
    return floor(x * scale) / scale


def import_signals():
    try:
        from PyQt5.QtCore import QObject, pyqtSignal

        return QObject, pyqtSignal
    except ImportError:
        return object, None
