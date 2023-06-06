# -*- mode: python ; coding: utf-8 -*-

import inspect
import tortoise.models
import galacteek.database.models.core
import galacteek.database.models.atomfeeds
import galacteek.database.models.pubsub
import galacteek.database.models.seeds
import galacteek.database.models.pubchattokens
import os
import multiaddr
from multiaddr.codecs import *


goIpfsVersion = os.getenv('KUBO_VERSION')
block_cipher = None


source_mods = [
    tortoise.models,
    galacteek.database.models.atomfeeds,
    galacteek.database.models.browser,
    galacteek.database.models.bm,
    galacteek.database.models.core,
    galacteek.database.models.pubsub,
    galacteek.database.models.pubchattokens,
    galacteek.database.models.seeds
]


def collect_source_files(modules):
    datas = []
    for module in modules:
        print('Collecting source for', module)
        source = inspect.getsourcefile(module)
        if source:
            dest = f"src.{module.__name__}"  # use "src." prefix
            datas.append((source, dest))
            print('Success: added', source, dest)
        else:
            print('Could not get source for', module)
    return datas


source_files = collect_source_files(source_mods)
source_files_toc = TOC((name, path, 'DATA') for path, name in source_files)


a = Analysis(['galacteek_win.py'],
             pathex=[
    "C:/Python37/Lib/site-packages/PyQt5/Qt/bin",
    "C:/Python37/Lib/site-packages/PyQt5/Qt",
    "C:/Python37/Lib/site-packages",
    "C:/Python37/Lib",
    "C:/Python37",
    "D:/a/galacteek/galacteek",
    "C:/hostedtoolcache/windows/python/3.7.9/x64/",
    "C:/hostedtoolcache/windows/python/3.7.9/x64/lib/site-packages/PyQt5/Qt/bin",
    "C:/hostedtoolcache/windows/python/3.7.9/x64/lib/site-packages/PyQt5/Qt"
    ],
    binaries=[
    ('./packaging/windows/libmagic/libmagic-1.dll',
     '.'),
    ('./packaging/windows/libmagic/libgnurx-0.dll',
     '.'),
    ('./packaging/windows/zbar/libzbar-64.dll',
     '.'),
    ('./packaging/windows/zbar/libiconv.dll',
     '.'),
    ('./packaging/windows/zbar/libiconv.dll',
     'pyzbar'),
    ('./notbit-cygwin/notbit.exe',
     'bin'),
    ('./notbit-cygwin/notbit-keygen.exe',
     'bin'),
    ('./notbit-cygwin/notbit-sendmail.exe',
     'bin'),
    ('./notbit-cygwin/cygwin1.dll',
     'bin'),
    ('./notbit-cygwin/cygcrypto-1.1.dll',
     'bin'),
    ('./notbit-cygwin/cygz.dll',
     'bin'),
    ('./kubo/ipfs.exe',
     '.'),
    ('./fs-repo-migrations/fs-repo-migrations.exe',
     '.'),
    ('./packaging/windows/tor/tor.exe',
     '.'),
    ('./packaging/windows/tor/tor-gencert.exe',
     '.')
    ],
    datas=[
    ('./packaging/windows/cygwin/fstab',
     'etc'),
    ('./packaging/windows/matplotlibrc',
     '.'),
    ('./packaging/windows/magic.mgc',
     '.'),
    ('./packaging/windows/matplotlibrc',
     'matplotlib/mpl-data')
    ],
    hiddenimports=[
        'multiaddr',
        'multiaddr.codecs.*',
        'omegaconf',
        'mode',
        'openai',
        'openai.*',
        'claptcha'
    ],
    hookspath=['packaging/windows/hooks'],
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'tcl',
        'tk',
        'sphinxcontrib',
        'tornado',
        'lib2to3',
        'PyInstaller',
        'pip',
        'setuptools',
        'pytest',
        'Cryptodome.SelfTest',
        'PIL.ImageQt'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False)

pyz = PYZ(a.pure, a.zipped_data,
          source_files_toc,
          cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='galacteek',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          icon='share/icons/galacteek.ico',
          console=True)
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='galacteek')
