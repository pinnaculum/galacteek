from PyQt5.QtGui import QFont


def _f(family, size, bold=False):
    f = QFont(family, size)
    if bold:
        f.setBold(True)
    return f


def fMontSerrat(size=14, bold=False):
    return _f('Montserrat', size, bold=bold)


def fInterUi(size=14, bold=False):
    return _f('Inter UI', size, bold=bold)
