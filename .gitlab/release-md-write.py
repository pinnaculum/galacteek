#!/usr/bin/env python

import sys
import os


appimage_url = os.environ.get('APPIMAGE_IPFS_URL')

vars = [
    'PRELUDE',
    'CHANGELOG',
    'CI_COMMIT_SHA',
    'CI_COMMIT_SHORT_SHA',
    'GALACTEEK_VERSION',
    'APPIMAGE_FILENAME',
    'APPIMAGE_IPFS_URL',
    'APPIMAGE_PATH',
    'FLATPAK_FILENAME',
    'FLATPAK_PATH',
    'FLATPAK_IPFS_URL'
]


prelude_ipfs_download = '''
## AppImage IPFS binary download

This release is distributed on the IPFS network.

You can [download it here]({url})
'''


with open('.gitlab/RELEASE.md.tmpl', 'rt') as fd:
    md = fd.read()

    if appimage_url:
        os.environ['PRELUDE'] = prelude_ipfs_download.format(
            url=appimage_url)

    for var in vars:
        value = os.environ.get(var, None)
        if value:
            md = md.replace(
                f"@@{var}@@",
                value
            )

    print(md, file=sys.stdout)
