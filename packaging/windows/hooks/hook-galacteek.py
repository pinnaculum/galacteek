from PyInstaller.utils.hooks import *


datas = []

try:
    datas += copy_metadata('galacteek.templates')
    datas += copy_metadata('galacteek.docs.manual')
    datas += copy_metadata('galacteek.docs.manual.en')
    datas += copy_metadata('galacteek.docs.manual.en.html')
except Exception as err:
    pass

hiddenimports = [
    'galacteek.templates',
    'galacteek.docs.manual',
    'galacteek.docs.manual.en',
    'galacteek.docs.manual.en.html',
    'markdown.extensions.attr_list'
]

datas += [('galacteek/templates', '_pkg/galacteek/templates')]
datas += [('galacteek/hashmarks', '_pkg/galacteek/hashmarks')]
datas += [('galacteek/docs/manual', '_pkg/galacteek/docs/manual')]

print(datas)
