from galacteek.ipfs.cid import make_cid

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
        multihash.decode(hashstring.encode('ascii'), 'base58')
        return True
    except BaseException:
        return False


def getCID(hashstring):
    try:
        return make_cid(hashstring)
    except BaseException:
        return None


def cidConvertBase32(multihash):
    """Convert a base58-encoded CIDv1 to base32"""

    cid = getCID(multihash)
    if not cid or cid.version != 1:
        return None
    return cid.encode('base32').decode()


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
        try:  # can raise ValueError
            if multihash.decode(c.multihash):
                return True
        except BaseException:
            return False
    elif c.version == 1:
        return True
    return False

# Regexps


ipfsPathRe = re.compile(
    r'^(\s*)?(?:fs:|ipfs:|dweb:)?(?P<fullpath>/ipfs/(?P<cid>[a-zA-Z0-9]{46,59}?)(?P<subpath>\/.*)?)$',  # noqa
    flags=re.MULTILINE)

ipfsPathGwRe = re.compile(
    r'^(\s*)?(?:https?://[a-zA-Z0-9:.]*)?(?P<fullpath>/ipfs/(?P<cid>[a-zA-Z0-9]{46,59}?)(?P<subpath>\/.*)?)$',  # noqa
    flags=re.MULTILINE)

ipfsCidRe = re.compile(
    r'^(\s*)?(?P<cid>[a-zA-Z0-9]{46,59})$', flags=re.MULTILINE)

ipnsPathRe = re.compile(
    r'^(\s*)?(?:fs:|ipfs:|dweb:)?(?P<fullpath>/ipns/([a-zA-Z0-9\.\-]*)(?P<subpath>\/.*)?$)',  # noqa
    flags=re.MULTILINE)

ipnsPathGwRe = re.compile(
    r'^(\s*)?(?:https?://[a-zA-Z0-9:.]*)?(?P<fullpath>/ipns/([a-zA-Z0-9\.\-]*)(?P<subpath>\/.*)?$)',  # noqa
    flags=re.MULTILINE)


def ipfsRegSearchPath(text):
    for reg in [ipfsPathRe, ipfsPathGwRe]:
        matched = reg.match(text)
        if matched:
            return matched
    return None


def ipfsRegSearchCid(text):
    return ipfsCidRe.match(text)


def ipnsRegSearchPath(text):
    for reg in [ipnsPathRe, ipnsPathGwRe]:
        matched = reg.match(text)
        if matched:
            return matched
    return None
