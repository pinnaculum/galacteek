import uuid
import socket
import re
import hashlib
import sys
import os
import pkg_resources
import pathlib
import platform
import tempfile

from datetime import datetime
from datetime import timezone
from dateutil import parser as duparser
from sys import version_info
from jsonschema import validate
from jsonschema import FormatChecker
from jsonschema.exceptions import ValidationError
from contextlib import closing


from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QFile


def inPyInstaller():
    if platform.system() == 'Windows':
        return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

    return False


def pyInstallerBundleFolder():
    return pathlib.Path(getattr(sys, '_MEIPASS'))


def pyInstallerPkgFolder():
    return pyInstallerBundleFolder().joinpath('_pkg')


def pkgResourcesListDir(pkg: str, rscName: str):
    # Simple wrapper around pkg_resources.resource_listdir

    if inPyInstaller():
        root = pyInstallerPkgFolder().joinpath(
            pkg.replace('.', os.sep)
        )
        if rscName != '':
            root = root.joinpath(rscName)

        try:
            return os.listdir(str(root))
        except Exception:
            return []
    else:
        return pkg_resources.resource_listdir(pkg, rscName)


def pkgResourcesDirEntries(pkg: str):
    for entry in pkgResourcesListDir(pkg, ''):
        if entry.startswith('_'):
            continue

        yield entry


def pkgResourcesRscFilename(pkg, rscName):
    # Simple wrapper around pkg_resources.resource_filename

    if inPyInstaller():
        root = pyInstallerPkgFolder().joinpath(
            pkg.replace('.', os.sep)
        )

        return str(root.joinpath(rscName))
    else:
        return pkg_resources.resource_filename(pkg, rscName)


def readQrcTextFile(path):
    try:
        qFile = QFile(path)
        qFile.open(QFile.ReadOnly)
        ba = qFile.readAll()
        return ba.data().decode()
    except BaseException:
        pass


def readQrcFileRaw(path):
    try:
        qFile = QFile(path)
        qFile.open(QFile.ReadOnly)
        ba = qFile.readAll()
        return bytes(ba.data())
    except BaseException:
        pass


def qrcWriteToTemp(path, delete=False):
    try:
        tmpf = tempfile.NamedTemporaryFile(delete=delete)
        qFile = QFile(path)
        qFile.open(QFile.ReadOnly)
        ba = qFile.readAll()
        data = ba.data()

        with open(tmpf.name, 'w+b') as fd:
            fd.write(data)

        return tmpf.name
    except BaseException:
        pass


def sha256Digest(value: str):
    s = hashlib.sha3_256()
    s.update(value.encode())
    return s.hexdigest()


def runningApp():
    return QApplication.instance()


def utcDatetime():
    return datetime.now(timezone.utc)


def utcDatetimeIso():
    return utcDatetime().isoformat()


def datetimeNow():
    return datetime.now()


def datetimeIsoH(timespec='seconds'):
    return datetimeNow().isoformat(sep=' ', timespec=timespec)


def parseDate(date):
    if isinstance(date, str):
        try:
            return duparser.parse(date)
        except Exception:
            pass


def validMimeType(mime):
    if isinstance(mime, str):
        # doesn't parse attributes
        return re.match(r'^[\w-]{1,32}/[\w-]{1,256}$', mime)

    return False


def doubleUid4():
    return str(uuid.uuid4()) + str(uuid.uuid4())


def uid4():
    return str(uuid.uuid4())


def isoformat(dt, sep=' ', timespec='seconds'):
    if version_info.major == 3 and version_info.minor < 6:
        return dt.isoformat(sep)
    elif version_info.major == 3 and version_info.minor >= 6:
        return dt.isoformat(sep, timespec=timespec)


def nonce():
    return str(uuid.uuid4())


def jsonSchemaValidate(data, schema, **opts):
    try:
        validate(data, schema, format_checker=FormatChecker())
    except ValidationError as err:
        print('jsonSchemaValidate error: {}'.format(err))
        return False
    else:
        return True


def unusedTcpPort():
    try:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.bind(('', 0))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            return s.getsockname()[1]
    except Exception:
        return None


class SingletonDecorator:
    def __init__(self, _class):
        self._class = _class
        self.instance = None

    def __call__(self, *args, **kwds):
        if self.instance is None:
            self.instance = self._class(*args, **kwds)

        return self.instance


def debugTrace():
    from PyQt5.QtCore import pyqtRemoveInputHook
    from pdb import set_trace

    pyqtRemoveInputHook()
    set_trace()


def secondsToTimeAgo(seconds: int) -> str:
    # There must be a better name ..

    h = seconds // 3600
    d = int(h / 24)
    m = seconds % 3600 // 60
    s = seconds % 3600 % 60

    if d > 0:
        return '{:02d} day(s) ago'.format(d)
    elif h > 0:
        return '{:02d} hour(s) ago'.format(h)
    elif m > 0:
        return '{:02d} minute(s) ago'.format(m)
    elif s > 0:
        return '{:02d} second(s) ago'.format(s)
    else:
        return 'some time ago'  # how dare you
