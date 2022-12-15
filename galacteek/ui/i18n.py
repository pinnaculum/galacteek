import inspect

from PyQt5.QtCore import QCoreApplication

from galacteek.i18n.actions import *  # noqa
from galacteek.i18n.ai import *  # noqa
from galacteek.i18n.blackhole import *  # noqa
from galacteek.i18n.browser import *  # noqa
from galacteek.i18n.bm import *  # noqa
from galacteek.i18n.bt import *  # noqa
from galacteek.i18n.clipboard import *  # noqa
from galacteek.i18n.conn import *  # noqa
from galacteek.i18n.credentials import *  # noqa
from galacteek.i18n.did import *  # noqa
from galacteek.i18n.hashmark import *  # noqa
from galacteek.i18n.ip import *  # noqa
from galacteek.i18n.ipfs import *  # noqa
from galacteek.i18n.ipfsd import *  # noqa
from galacteek.i18n.lang import *  # noqa
from galacteek.i18n.ld import *  # noqa
from galacteek.i18n.mfs import *  # noqa
from galacteek.i18n.misc import *  # noqa
from galacteek.i18n.mplayer import *  # noqa
from galacteek.i18n.peers import *  # noqa
from galacteek.i18n.pin import *  # noqa
from galacteek.i18n.quickaccess import *  # noqa
from galacteek.i18n.search import *  # noqa
from galacteek.i18n.settings import *  # noqa
from galacteek.i18n.treeview import *  # noqa


def qtr(ctx, msg):
    return QCoreApplication.translate(ctx, msg)


def trTodo(msg):
    frm = inspect.stack()[2]
    mod = inspect.getmodule(frm[0])
    return QCoreApplication.translate(mod.__name__, msg)
