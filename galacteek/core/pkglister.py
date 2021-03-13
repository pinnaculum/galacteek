from cachetools import cached
from cachetools import LRUCache

import pkgutil
import importlib
import re

from galacteek.core import inPyInstaller


@cached(LRUCache(1))
def tocGet():
    toc = set()

    for importer in pkgutil.iter_importers('galacteek'):
        if hasattr(importer, 'toc'):
            toc |= importer.toc

    return toc


def pkgListPackages(pkgName: str):
    """
    Lists packages names in a package given its name

    Yields (pkg, fullname) tuples
    """

    if inPyInstaller():
        # From pyinstaller, pkgutil.iter_modules() doesn't work AFAIK
        # Use the TOC instead

        toc = tocGet()

        for fname in toc:
            if fname.startswith(pkgName):
                match = re.search(
                    rf'{pkgName}\.([a-zA-Z0-9]+)$',
                    fname
                )
                if match:
                    yield (match.group(1), fname)
    else:
        try:
            pkg = importlib.import_module(pkgName)
            for imp, modname, isPkg in pkgutil.iter_modules(pkg.__path__):
                if not isPkg:
                    continue

                yield (modname, f'{pkgName}.{modname}')
        except Exception:
            pass
