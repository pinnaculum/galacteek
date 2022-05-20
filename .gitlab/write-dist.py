#!/usr/bin/env python

import sys
import argparse

from omegaconf import OmegaConf


parser = argparse.ArgumentParser()
parser.add_argument('--template',
                    dest='tmpl')
parser.add_argument('--dst', dest='dest')
args = parser.parse_args()

if not args.tmpl:
    print('Invalid options')
    sys.exit(1)


try:
    manifest = OmegaConf.load(args.tmpl)
    c = OmegaConf.to_container(manifest, resolve=True)
    OmegaConf.save(c, args.dest)
except Exception as err:
    print(err)
    sys.exit(1)

sys.exit(0)
