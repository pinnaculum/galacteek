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
    'APPIMAGE_DIR_CID',
    'APPIMAGE_IPFS_URL',
    'APPIMAGE_PATH',
    'FLATPAK_FILENAME',
    'FLATPAK_PATH',
    'FLATPAK_IPFS_URL'
]


prelude_ipfs_download = '''
## AppImage IPFS binary download

This release is distributed on the IPFS network !

You can [download it here]({url})

If you run an IPFS node and want to help distributing this software, you
can do so by run the following command:

```
ipfs pin add -r @@APPIMAGE_DIR_CID@@
./@@APPIMAGE_FILENAME@@
```
'''

prelude_no_ipfs_download = '''
The AppImage for this release is only distributed via GitLab packages.
'''


def replace(msg):
    for var in vars:
        value = os.environ.get(var, None)
        if value:
            msg = msg.replace(
                f"@@{var}@@",
                value
            )

    return msg


with open('.gitlab/RELEASE.md.tmpl', 'rt') as fd:
    md = fd.read()

    if appimage_url:
        os.environ['PRELUDE'] = replace(prelude_ipfs_download.format(
            url=appimage_url))
    else:
        os.environ['PRELUDE'] = replace(prelude_no_ipfs_download)

    print(replace(md), file=sys.stdout)
