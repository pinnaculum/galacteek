import os
import os.path
import re
import sys
import subprocess
import shutil
import codecs
import json
from pathlib import Path

from setuptools import setup
from setuptools import Command
from setuptools import find_packages
from distutils.command.build import build
from distutils.version import StrictVersion

PY_VER = sys.version_info

if PY_VER >= (3, 6):
    pass
else:
    print('You need python3.6 or newer')
    print('Your python version is {0}'.format(PY_VER))
    raise RuntimeError('Invalid python version')


with codecs.open(os.path.join(os.path.abspath(os.path.dirname(
        __file__)), 'galacteek', '__version__.py'), 'r', 'latin1') as fp:
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
    user_options = [
        ("all=", None, "Build all docs"),
    ]

    def initialize_options(self):
        self.all = None

    def finalize_options(self):
        pass

    def run(self):
        args = [
            'sphinx-build', '-b', 'html',
            'galacteek/docs/manual/en',
            'galacteek/docs/manual/en/html'
        ]

        if self.all:
            args.append('-a')

        os.system(' '.join(args))


class build_contracts(Command):
    user_options = [
        ("deploy=", None, "Deploy given contracts"),
        ("contracts=", None, "Contracts list to build"),
        ("rpcurl=", None, "Ethereum RPC url"),
    ]

    def initialize_options(self):
        self.deploy = None
        self.contracts = None
        self.rpcurl = 'http://127.0.0.1:7545'

    def finalize_options(self):
        pass

    def run(self):
        from galacteek.smartcontracts import listContracts
        from galacteek.smartcontracts import solCompileFile
        from galacteek.smartcontracts import vyperCompileFile
        from galacteek.blockchain.ethereum.contract import contractDeploy
        from galacteek.blockchain.ethereum.ctrl import web3Connect

        cdeploy = [c for c in self.deploy.split(',')] if \
            self.deploy else []

        w3 = web3Connect(self.rpcurl)

        for contract in listContracts():
            print('>', contract, contract.dir)

            ifacePath = os.path.join(contract.dir, 'interface.json')

            if contract.type == 'vyper':
                iface = vyperCompileFile(contract.sourcePath)
                if not iface:
                    print('Error compiling vyper contract')
                    continue
            elif contract.type == 'solidity':
                compiled = solCompileFile(contract.sourcePath)
                if not compiled:
                    print('Error compiling solidity contract')
                    continue
                contractId, iface = compiled.popitem()
            else:
                continue

            try:
                with open(ifacePath, 'w+t') as ifacefd:
                    ifacefd.write(json.dumps(iface, indent=4))
            except Exception as err:
                print(str(err))
            else:
                print(contract.name, 'compiled')
                if contract.name in cdeploy:
                    addr = contractDeploy(w3, iface)
                    print(contract.name, 'deployed at', addr)


class build_ui(Command):
    user_options = [
        ("tasks=", None, 'Tasks'),
        ("uiforms=", None, "UI forms list to build, separated by ','"),
        ("themes=", None, "Themes ','")
    ]

    def initialize_options(self):
        self.uiforms = None
        self.tasks = 'forms,themes'
        self.themes = '*'

        # Forms where we don't want to have automatic slots
        # connection with connectSlotsByName()
        self.uiforms_noSlotConnect = [
            Path('galacteek/ui/forms/browsertab.ui'),
            Path('galacteek/ui/forms/dagview.ui'),
            Path('galacteek/ui/forms/files.ui'),
            Path('galacteek/ui/forms/qschemecreatemapping.ui')
        ]

    def finalize_options(self):
        pass

    def filterUic(self, uifile, uicpath):
        if uifile in self.uiforms_noSlotConnect:
            print('* {ui}: Removing automatic slots connection'.format(
                ui=uifile))

            with open(str(uicpath), 'rt') as fd:
                code = fd.read()

            nCode = re.sub(
                r'^\s*QtCore.QMetaObject.connectSlotsByName.*\n$', '',
                code,
                flags=re.MULTILINE
            )

            with open(str(uicpath), 'wt') as fd:
                print('* {ui}: Rewriting {path}'.format(
                    ui=uifile, path=uicpath))
                fd.write(nCode)

    def run(self):
        from galacteek.ui.themes import themesCompileAll

        uifiles = []
        uidir = Path('galacteek/ui')
        formsdir = Path('galacteek/ui/forms')

        tasks = self.tasks.split(',')

        if self.uiforms:
            uifiles = [formsdir.joinpath(f'{form}.ui') for form
                       in self.uiforms.split(',')]
        else:
            uifiles = formsdir.glob('*.ui')

        if 'forms' in tasks:
            for uifile in uifiles:
                print('* Building UI form:', uifile)

                fp_out = formsdir.joinpath(
                    'ui_{}'.format(
                        uifile.name.replace('.ui', '.py'))
                )

                run(['pyuic5',
                     '--from-imports',
                     str(uifile),
                     '-o',
                     str(fp_out)])

                self.filterUic(uifile, fp_out)

            run(['pylupdate5', '-verbose', 'galacteek.pro'])

            trdir = Path('./share/translations')
            lrelease = shutil.which('lrelease-qt5')

            if not lrelease:
                lrelease = shutil.which('lrelease')

            for lang in ['en', 'es', 'fr']:
                if lrelease:
                    run([lrelease,
                         str(trdir.joinpath(f'galacteek_{lang}.ts')),
                         '-qm',
                         str(trdir.joinpath(f'galacteek_{lang}.qm'))])
                else:
                    print('lrelease was not found'
                          ', cannot build translation files')

            qrcPath = uidir.joinpath('galacteek.qrc')
            qrcCPath = formsdir.joinpath('galacteek_rc.py')

            run(['pyrcc5', str(qrcPath), '-o',
                 str(qrcCPath)])

        if 'themes' in tasks:
            themesCompileAll()


class vbump(Command):
    """
    revbump command
    """
    user_options = [
        ("version=", None, 'Version')
    ]

    def initialize_options(self):
        self.version = None

    def finalize_options(self):
        pass

    def run(self):
        if not self.version:
            raise ValueError('No version specified')

        v = StrictVersion(self.version)
        assert v.version[0] is not None
        assert v.version[1] is not None
        assert v.version[2] is not None

        with open('galacteek/VERSION', 'wt') as f:
            f.write(f'{self.version}\n')

        os.system('git add galacteek/VERSION')

        with open('galacteek/__version__.py', 'wt') as f:
            f.write(f"__version__ = '{self.version}'\n")

        os.system('git add galacteek/__version__.py')

        with open('packaging/windows/galacteek-installer.nsi',
                  'rt') as f:
            data = f.read()
            data = re.sub(
                r'(\!define VERSIONMAJOR) (\d*)',
                rf'\1 {v.version[0]}',
                data
            )
            data = re.sub(
                r'(\!define VERSIONMINOR) (\d*)',
                rf'\1 {v.version[1]}',
                data
            )
            data = re.sub(
                r'(\!define VERSIONBUILD) (\d*)',
                rf'\1 {v.version[2]}',
                data
            )

        with open('packaging/windows/galacteek-installer.nsi',
                  'wt') as f:
            f.write(data)

        os.system('git add packaging/windows/galacteek-installer.nsi')


class _build(build):
    sub_commands = [('build_ui', None)] + build.sub_commands


with open('README.rst', 'r') as fh:
    long_description = fh.read()

deps_links = []


def reqs_parse(path):
    reqs = []
    deps = []

    with open(path) as f:
        lines = f.read().splitlines()
        for line in lines:
            if line.startswith('-e'):
                link = line.split().pop()
                deps.append(link)
            else:
                reqs.append(line)

    return reqs


install_reqs = reqs_parse('requirements.txt')
install_reqs_extra_markdown = reqs_parse('requirements-extra-markdown.txt')
install_reqs_extra_matplotlib = reqs_parse('requirements-extra-matplotlib.txt')
install_reqs_docs = reqs_parse('requirements-docs.txt')
install_reqs_ui_pyqt_513 = reqs_parse('requirements-ui-pyqt-5.13.txt')
install_reqs_ui_pyqt_515 = reqs_parse('requirements-ui-pyqt-5.15.txt')
install_reqs_ld_schemas = reqs_parse('requirements-ld-schemas.txt')
install_reqs_rdf_bsddb = reqs_parse('requirements-rdf-bsddb.txt')
install_reqs_trafficshaping = reqs_parse('requirements-trafficshaping.txt')


found_packages = find_packages(exclude=['tests', 'tests.*'])

setup(
    name='galacteek',
    version=version,
    license='GPL3',
    author='cipres',
    author_email='BM-87dtCqLxqnpwzUyjzL8etxGK8MQQrhnxnt1@bitmessage',
    url='https://gitlab.com/galacteek/galacteek',
    description='Browser for the distributed web',
    long_description=long_description,
    include_package_data=True,
    cmdclass={
        'build': _build,
        'build_ui': build_ui,
        'build_docs': build_docs,
        'build_contracts': build_contracts,
        'vbump': vbump
    },
    packages=found_packages,
    install_requires=install_reqs,
    extras_require={
        'ld-schemas': install_reqs_ld_schemas,
        'markdown-extensions': install_reqs_extra_markdown,
        'ui-pyqt-5.13': install_reqs_ui_pyqt_513,
        'ui-pyqt-5.15': install_reqs_ui_pyqt_515,
        'rdf-bsddb': install_reqs_rdf_bsddb,
        'trafficshaping': install_reqs_trafficshaping,
        'matplotlib': install_reqs_extra_matplotlib,
        'docs': install_reqs_docs,
    },
    dependency_links=deps_links,
    package_data={
        '': [
            '*.yaml',
            '*.qss',
            '*.css',
            '*.qrc',
            '*.qml',
            '*.jinja2',
            '*.rq'
        ],
        'galacteek': [
            'docs/manual/en/html/*.html',
            'docs/manual/en/html/_images/*',
            'docs/manual/en/html/_static/*',
            'ipfs/p2pservices/gemini/gem-localhost*',
            'ld/contexts/*',
            'ld/contexts/messages/*',
            'ld/contexts/services/*',
            'templates/*.html',
            'templates/assets/js/*.js',
            'templates/assets/css/*.css',
            'templates/ipid/*.html',
            'templates/layouts/*',
            'templates/ld/*.jinja2',
            'templates/ld/components/*/*.jinja2',
            'templates/ld/lib/*.jinja2',
            'templates/usersite/*.html',
            'templates/usersite/assets/*',
            'templates/usersite/assets/css/*',
            'templates/usersite/macros/*',
            'templates/imggallery/*.html',
            'hashmarks/default/*.yaml'
        ]
    },
    entry_points={
        'gui_scripts': [
            'galacteek = galacteek.guientrypoint:start'
        ],
        'console_scripts': [
            'galacteek-eth-master = galacteek.entrypoints.ethtool:ethTool',
            'galacteek-rdfifier = galacteek.entrypoints.rdfifier:rdfifier',
            'galacteek-eterna = galacteek.entrypoints.rdfifier:rdfifier'
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
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9'
    ],
    keywords=[
        'asyncio',
        'aiohttp',
        'ipfs'
    ]
)
