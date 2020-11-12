from PyInstaller.utils.hooks import *


datas = []

try:
    datas += copy_metadata('galacteek.templates')
    datas += copy_metadata('galacteek.docs.manual')
    datas += copy_metadata('galacteek.docs.manual.en')
    datas += copy_metadata('galacteek.docs.manual.en.html')
    datas += copy_metadata('random_username')
    datas += copy_metadata('random_username.data')
except Exception as err:
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
    'aioipfs'
]

excludedimports = [
    'tkinter',
    'tcl',
    'tk',
    'sphinxcontrib',
    'tornado',
    'lib2to3'
]

datas += [('galacteek/templates', '_pkg/galacteek/templates')]
datas += [('galacteek/hashmarks', '_pkg/galacteek/hashmarks')]
datas += [('galacteek/docs/manual', '_pkg/galacteek/docs/manual')]
datas += [('packaging/windows/random_username', 'random_username')]
datas += [('magic.mgc', '.')]

print(datas)
