import os
import os.path
from pathlib import Path

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

    # Settings forms (they are dynamically loaded)
    'galacteek.ui.forms.ui_settings_center',
    'galacteek.ui.forms.ui_settings_files',
    'galacteek.ui.forms.ui_settings_general',
    'galacteek.ui.forms.ui_settings_ipfs',
    'galacteek.ui.forms.ui_settings_pinning',
    'galacteek.ui.forms.ui_settings',
    'galacteek.ui.forms.ui_settings_ui',

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

pkgrDest = '_pkg'

datas += [('galacteek/templates', f'{pkgrDest}/galacteek/templates')]
datas += [('galacteek/ui/themes', f'{pkgrDest}/galacteek/ui/themes')]
datas += [('galacteek/hashmarks', f'{pkgrDest}/galacteek/hashmarks')]
datas += [('galacteek/docs/manual', f'{pkgrDest}/galacteek/docs/manual')]
datas += [('galacteek/ld/contexts', f'{pkgrDest}/galacteek/ld/contexts')]
datas += [('packaging/windows/random_username', 'random_username')]
datas += [('magic.mgc', '.')]

for root, dirs, files in os.walk('galacteek'):
    for file in files:
        if file.endswith('.yaml'):
            p = Path(root).joinpath(file)
            dst = Path(pkgrDest).joinpath(str(p.parent).lstrip('/'))
            datas += [(str(p), str(dst))]

            print(f'YAML file copied from {p} to {dst}')

for elem in datas:
    print(elem)
