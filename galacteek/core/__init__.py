from datetime import datetime
from datetime import timezone
from dateutil import parser as duparser
from sys import version_info
from jsonschema import validate
from jsonschema.exceptions import ValidationError


from PyQt5.QtWidgets import QApplication


def runningApp():
    return QApplication.instance()


def utcDatetime():
    return datetime.now(timezone.utc)


def utcDatetimeIso():
    return utcDatetime().isoformat()


def datetimeIsoH():
    return datetime.now().isoformat(sep=' ')


def parseDate(date):
    if isinstance(date, str):
        try:
            return duparser.parse(date)
        except Exception:
            pass


def isoformat(dt, sep=' ', timespec='seconds'):
    if version_info.major == 3 and version_info.minor < 6:
        return dt.isoformat(sep)
    elif version_info.major == 3 and version_info.minor >= 6:
        return dt.isoformat(sep, timespec=timespec)


def jsonSchemaValidate(data, schema):
    try:
        validate(data, schema)
    except ValidationError:
        return False
    else:
        return True
