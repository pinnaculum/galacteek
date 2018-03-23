import os, os.path, re
import sys
import codecs
import subprocess
from setuptools import setup, find_packages, Command
from distutils.command.build import build

PY_VER = sys.version_info

if PY_VER >= (3, 5):
    pass
else:
    raise RuntimeError("You need python 3.5 or newer (need async support)")

with codecs.open(os.path.join(os.path.abspath(os.path.dirname(
        __file__)), 'galacteek', '__init__.py'), 'r', 'latin1') as fp:
    try:
        version = re.findall(r"^__version__ = '([^']+)'\r?$",
                             fp.read(), re.M)[0]
    except IndexError:
        raise RuntimeError('Unable to determine version.')

def run(*args):
    p = subprocess.Popen(*args,
            stdout=subprocess.PIPE)
    stdout, err = p.communicate()
    return stdout

class build_ui(Command):
    user_options = [ ]

    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        uidir = 'galacteek/ui'
        dstdir = uidir
        uifiles = ['galacteek',
                'browsertab',
                'files',
                'keys',
                'addkeydialog',
                'mediaplayer',
                'settings',
                'newdocument']
        for uifile in uifiles:
            print('Updating UI file:', uifile)

            run(['pyuic5', '--from-imports',
                '{0}/{1}.ui'.format(uidir, uifile),
                '-o',
                '{0}/ui_{1}.py'.format(dstdir, uifile)
                ])

        run(['pylupdate5', '-verbose', 'galacteek.pro'])

        trdir = './share/translations'
        for lang in ['en']:
            run(['lrelease-qt5',
                '{0}/galacteek_{1}.ts'.format(trdir, lang),
                '-qm',
                '{0}/galacteek_{1}.qm'.format(trdir, lang)
                ])

        run(['pyrcc5',
            '{0}/galacteek.qrc'.format(uidir), '-o',
            '{0}/galacteek_rc.py'.format(uidir)])

class _build(build):
    sub_commands = [('build_ui', None)] + build.sub_commands

setup(
    name='galacteek',
    version=version,
    license='AGPL3',
    author='David Ferlier',
    url='https://gitlab.com/cipres/galacteek',
    description='IPFS navigator',
    include_package_data=False,
    cmdclass={'build': _build, 'build_ui': build_ui},
    packages=[
        'galacteek',
        'galacteek.core',
        'galacteek.ipfs',
        'galacteek.ui'
    ],
    install_requires=[
        'aiohttp',
        'aiofiles',
        'async_generator>=1.0',
        'yarl',
        'base58',
        'py-cid',
    ],
    entry_points={
        'gui_scripts': [
            'galacteek = galacteek.guientrypoint:start',
        ]
    },
    classifiers=[
        'Environment :: X11 Applications :: Qt',
        'Topic :: Desktop Environment :: File Managers',
        'Topic :: Internet :: WWW/HTTP :: Browsers',
        'Programming Language :: Python',
        'Intended Audience :: Developers',
        'Development Status :: 4 - Beta',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: GNU Affero General Public License v3',
        'Topic :: System :: Filesystems',
    ],
    keywords=[
        'async',
        'aiohttp',
        'ipfs'
    ]
)
