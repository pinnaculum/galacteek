#!/usr/bin/env python3

import keepachangelog
import sys

try:
    version = sys.argv[1]
    raw = keepachangelog.to_raw_dict("CHANGELOG.md")
    changes = raw[version]

    print(changes['raw'])
except Exception:
    pass
