
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

# Regexps

ipfsPathRe = re.compile(
    '^(\s*)?(?:fs:|ipfs:)?(?P<fullpath>/ipfs/(?P<cid>[a-zA-Z0-9]{46,49}?)(?P<subpath>\/.*)?)$',
    flags=re.MULTILINE)

ipfsCidRe = re.compile(
    '^(\s*)?(?P<cid>[a-zA-Z0-9]{46,49})$', flags=re.MULTILINE)

ipnsPathRe = re.compile(
    '^(\s*)?(?:fs:|ipfs:)?(?P<fullpath>/ipns/([a-zA-Z0-9\.\-]*)(?P<subpath>\/.*)?$)',
    flags=re.MULTILINE)

def ipfsRegSearchPath(text):
    return ipfsPathRe.match(text)

def ipfsRegSearchCid(text):
    return ipfsCidRe.match(text)

def ipnsRegSearchPath(text):
    return ipnsPathRe.match(text)
