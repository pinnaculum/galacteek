import os
import os.path
import traceback
from pathlib import Path

from PyInstaller.utils.hooks import *
from PyInstaller.compat import modname_tkinter

datas = []
binaries = []

try:
    datas += copy_metadata('random_username')
    datas += copy_metadata('frozendict')
    datas += copy_metadata('mkdocs')
    datas += copy_metadata('mkdocs-bootswatch')
except Exception:
    traceback.print_exc()

hiddenimports = [
    'bsddb3',

    'rdflib',
    'rdflib_jsonld',
    'rdflib_pyld_compat',
    'rdflib_sqlalchemy',
    'rdflib_sqlite',

    'markdown.extensions',
    'markdown.extensions.attr_list',
    'random_username',
    'random_username.data',
    'PyQt5',
    'tortoise',
    'tortoise.fields',
    'tortoise.backends',
    'tortoise.backends.sqlite',
    'tortoise.backends.base',
    'aiohttp',
    'aioipfs',
    'frozendict',
    'mkdocs',
    'mkdocs-bootswatch'
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
    'multiaddr.codecs.utf8',
    'multiaddr.codecs._util'
]

hiddenimports += collect_submodules('mkdocs')

hiddenimports += collect_submodules('rdflib')
hiddenimports += collect_submodules('rdflib_jsonld')
hiddenimports += collect_submodules('rdflib_sqlalchemy')
hiddenimports += collect_submodules('rdflib_sqlite')
hiddenimports += collect_submodules('rdflib_pyld_compat')

hiddenimports += collect_submodules('pkg_resources')
hiddenimports += collect_submodules('setuptools')
hiddenimports += collect_submodules('distutils')

pip_datas, pip_binaries, pip_hiddenimports = collect_all('pip', include_py_files=True)

# :\
pip_binaries += [
    'venvg/Scripts/pip.exe',
    'venvg/Scripts/pip3.exe',
    'venvg/Scripts/pip3.7.exe'
]

print('pip binaries', pip_binaries)

hiddenimports += pip_hiddenimports
binaries += pip_binaries
datas += pip_datas

print('>>>>', binaries)


for imp in hiddenimports:
    print(f'Hidden import: {imp}')


for binary in binaries:
    print(f'Including binary: {binary}')

excludedimports = [
    'tkinter',
    'tcl',
    'tk',
    'sphinxcontrib',
    'tornado',
    'lib2to3'
    # modname_tkinter
]

pkgrDest = '_pkg'

datas += [('galacteek/templates', f'{pkgrDest}/galacteek/templates')]
datas += [('galacteek/ui/themes', f'{pkgrDest}/galacteek/ui/themes')]
datas += [('galacteek/hashmarks', f'{pkgrDest}/galacteek/hashmarks')]
datas += [('galacteek/docs/manual', f'{pkgrDest}/galacteek/docs/manual')]
# datas += [('galacteek-ld-web4/galacteek_ld_web4',
#            f'{pkgrDest}/galacteek_ld_web4')]
datas += [('packaging/windows/random_username', 'random_username')]

for root, dirs, files in os.walk('galacteek'):
    for file in files:
        if file.endswith('.yaml'):
            p = Path(root).joinpath(file)
            dst = Path(pkgrDest).joinpath(str(p.parent).lstrip('/'))
            datas += [(str(p), str(dst))]

            print(f'YAML file copied from {p} to {dst}')

for elem in datas:
    print(f'Data: {elem}')
