
from galacteek.ipfs.cid import make_cid, CIDv0, CIDv1

import multihash
import re

def isMultihash(hashstring):
    """
    Check if hashstring is a valid base58-encoded multihash

    :param str hashstring: the multihash to validate
    :return: if the value is a valid multihash or not
    :rtype: bool
    """
    try:
        mh = multihash.decode(hashstring.encode('ascii'), 'base58')
        return True
    except:
        return False

def getCID(hashstring):
    try:
        return make_cid(hashstring)
    except:
        return None

def cidValid(cidstring):
    """
    Check if cidstring is a valid IPFS CID

    :param str cidstring: the CID to validate
    :return: if the value is a valid CID or not
    :rtype: bool
    """

    c = getCID(cidstring)
    if c is None:
        return False
    if c.version == 0:
        # Ensure that we can decode the multihash
        try: # can raise ValueError
            if multihash.decode(c.multihash):
                return True
        except:
            return False
    elif c.version == 1:
        return True
    return False

def ipfsRegSearch(text):
    return re.search('/ipfs/([a-zA-Z0-9]*)(\/.*$)?', text)

def ipnsRegSearch(text):
    return re.search('/ipns/([a-zA-Z0-9\.]*)(\/.*$)?', text)
