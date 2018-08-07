import os, os.path, re
import sys
import codecs
import subprocess
import glob
import shutil
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
    p = subprocess.Popen(*args, stdout=subprocess.PIPE)
    stdout, err = p.communicate()
    return stdout

class build_docs(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        from sphinx import build_main
        build_main([sys.argv[0], '-b', 'html',
            'galacteek/docs/manual/en', 'galacteek/docs/manual/en/html'])

class build_ui(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        uidir = 'galacteek/ui'
        dstdir = uidir

        for uifile in glob.iglob('{}/*.ui'.format(uidir)):
            print('Updating UI:', uifile)
            base = os.path.basename(uifile).replace('.ui', '')
            out = 'ui_{}.py'.format(base)

            run(['pyuic5', '--from-imports',
                uifile,
                '-o',
                os.path.join(uidir, out)
                ])

        run(['pylupdate5', '-verbose', 'galacteek.pro'])

        trdir = './share/translations'
        lrelease = shutil.which('lrelease-qt5')

        if not lrelease:
            lrelease = shutil.which('lrelease')

        for lang in ['en', 'fr']:
            if lrelease:
                run([lrelease,
                    os.path.join(trdir, 'galacteek_{}.ts'.format(lang)),
                    '-qm',
                    os.path.join(trdir, 'galacteek_{}.qm'.format(lang)),
                    ])
            else:
                print('lrelease was not found, cannot build translation files')

        run(['pyrcc5', os.path.join(uidir, 'galacteek.qrc'), '-o',
            os.path.join(uidir, 'galacteek_rc.py')])

class _build(build):
    sub_commands = [('build_ui', None)] + build.sub_commands

with open("README.rst", "r") as fh:
    long_description = fh.read()

setup(
    name='galacteek',
    version=version,
    license='GPL3',
    author='David Ferlier',
    author_email='galacteek@gmx.co.uk',
    url='https://gitlab.com/galacteek/galacteek',
    description='IPFS browser',
    long_description=long_description,
    long_description_content_type='text/x-rst',
    include_package_data=True,
    cmdclass={'build': _build, 'build_ui': build_ui, 'build_docs': build_docs},
    packages=[
        'galacteek',
        'galacteek.docs',
        'galacteek.docs.manual',
        'galacteek.core',
        'galacteek.ipfs',
        'galacteek.hashmarks',
        'galacteek.hashmarks.default',
        'galacteek.ui'
    ],
    install_requires=[
        'aioipfs',
        'aiohttp',
        'aiofiles',
        'async_generator>=1.0',
        'yarl',
        'base58',
        'py-multibase',
        'py-multicodec',
        'pymultihash',
        'Jinja2',
        'GitPython',
        'Sphinx>=1.4.8',
        'quamash',
        'PyQt5==5.10.1'
    ],
    package_data={
        'galacteek': [
             'docs/manual/en/html/*.html',
             'docs/manual/en/html/_images/*',
             'docs/manual/en/html/_static/*',
            'templates/*.html',
            'hashmarks/default/*.json'
        ]
    },
    entry_points={
        'gui_scripts': [
            'galacteek = galacteek.guientrypoint:start',
        ]
    },
    classifiers=[
        'Environment :: X11 Applications :: Qt',
        'Framework :: AsyncIO',
        'Topic :: Desktop Environment :: File Managers',
        'Topic :: Internet :: WWW/HTTP :: Browsers',
        'Development Status :: 4 - Beta',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Topic :: System :: Filesystems',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    keywords=[
        'asyncio',
        'aiohttp',
        'ipfs'
    ]
)
