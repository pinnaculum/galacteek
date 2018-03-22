
from cid.cid import make_cid, CIDv1

import multihash

def is_multihash(hashstring):
    try:
        mh = multihash.decode(hashstring.encode('ascii'), 'base58')
        return True
    except:
        return False
