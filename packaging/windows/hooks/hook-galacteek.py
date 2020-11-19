from PyInstaller.utils.hooks import *
from PyInstaller.compat import modname_tkinter


datas = []

try:
    datas += copy_metadata('galacteek.templates')
    datas += copy_metadata('galacteek.docs.manual')
    datas += copy_metadata('galacteek.docs.manual.en')
    datas += copy_metadata('galacteek.docs.manual.en.html')
    datas += copy_metadata('random_username')
    datas += copy_metadata('random_username.data')
except Exception:
    pass

hiddenimports = [
    'galacteek.templates',
    'galacteek.docs.manual',
    'galacteek.docs.manual.en',
    'galacteek.docs.manual.en.html',
    'markdown.extensions',
    'markdown.extensions.attr_list',
    'random_username',
    'random_username.data',
    'PyQt5',
    'galacteek',
    'tortoise',
    'tortoise.fields',
    'tortoise.backends',
    'tortoise.backends.sqlite',
    'tortoise.backends.base',
    'aiohttp',
    'aioipfs'
]

# We have to manually list multiaddr.codecs modules
# (using multiaddr.codecs.* fails)


hiddenimports += [
    'multiaddr',
    'multiaddr.codecs.fspath',
    'multiaddr.codecs.idna',
    'multiaddr.codecs.ip4',
    'multiaddr.codecs.ip6',
    'multiaddr.codecs.onion3',
    'multiaddr.codecs.onion',
    'multiaddr.codecs.p2p',
    'multiaddr.codecs.uint16be',
    'multiaddr.codecs.utf8'
    'multiaddr.codecs._util'
]


excludedimports = [
    'tkinter',
    'tcl',
    'tk',
    'sphinxcontrib',
    'tornado',
    'lib2to3',
    modname_tkinter
]

datas += [('galacteek/templates', '_pkg/galacteek/templates')]
datas += [('galacteek/hashmarks', '_pkg/galacteek/hashmarks')]
datas += [('galacteek/docs/manual', '_pkg/galacteek/docs/manual')]
datas += [('galacteek/ld/contexts', '_pkg/galacteek/ld/contexts')]
datas += [('packaging/windows/random_username', 'random_username')]
datas += [('magic.mgc', '.')]

print(datas)
