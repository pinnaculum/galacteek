from PyInstaller.utils.hooks import *


datas = []

try:
    datas += copy_metadata('galacteek.templates')
    datas += copy_metadata('galacteek.docs.manual')
    datas += copy_metadata('galacteek.docs.manual.en')
    datas += copy_metadata('galacteek.docs.manual.en.html')
    datas += copy_metadata('random_username')
except Exception as err:
    pass

hiddenimports = [
    'galacteek.templates',
    'galacteek.docs.manual',
    'galacteek.docs.manual.en',
    'galacteek.docs.manual.en.html',
    'markdown.extensions',
    'random_username',
    'PyQt5',
    'galacteek',
    'tortoise',
    'tortoise.fields',
    'tortoise.backends',
    'tortoise.backends.sqlite',
    'tortoise.backends.base',
    'aioipfs'
]

datas += [('galacteek/templates', '_pkg/galacteek/templates')]
datas += [('galacteek/hashmarks', '_pkg/galacteek/hashmarks')]
datas += [('galacteek/docs/manual', '_pkg/galacteek/docs/manual')]
datas += [('venvg/Lib/site-packages/random_username/data',
           'random_username/data')]

print(datas)
