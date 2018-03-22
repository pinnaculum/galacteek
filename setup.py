import os, os.path, re
import sys
import codecs
from setuptools import setup, find_packages

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

setup(
    name='galacteek',
    version=version,
    license='AGPL3',
    author='David Ferlier',
    url='https://gitlab.com/cipres/galacteek',
    description='IPFS navigator',
    include_package_data=False,
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
