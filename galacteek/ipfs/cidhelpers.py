import aioipfs

from PyQt5.QtCore import QUrl

from galacteek import log
from galacteek.ipfs.cid import make_cid
from galacteek.ipfs.stat import StatInfo

import multihash
import re
import os.path


def joinIpfs(path):
    if isinstance(path, str):
        return os.path.join('/ipfs/', path)


def joinIpns(path):
    if isinstance(path, str):
        return os.path.join('/ipns/', path)


def stripIpfs(path):
    if isinstance(path, str):
        return path.lstrip('/ipfs/')


def isIpfsPath(path):
    if isinstance(path, str):
        return ipfsRegSearchPath(path) is not None


def isIpnsPath(path):
    if isinstance(path, str):
        return ipnsRegSearchPath(path) is not None


def shortCidRepr(cid):
    cidStr = str(cid)
    if cid.version == 0:
        return '...{0}'.format(cidStr[3 * int(len(cidStr) / 5):])
    else:
        return '...{0}'.format(cidStr[4 * int(len(cidStr) / 5):])


def shortPathRepr(path):
    if isIpfsPath(path) or isIpnsPath(path):
        basename = os.path.basename(path)
        if cidValid(basename):
            cid = getCID(basename)
            return shortCidRepr(cid)
        else:
            return basename
    else:
        cid = getCID(path)
        if cid:
            return shortCidRepr(cid)
        else:
            return path


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
    """
    Convert a base58-encoded CIDv1 to base32

    :rtype: str
    """

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
    r'^(\s*)?(?:fs:(\/*)|ipfs:|dweb:(\/*)?|https?://[a-zA-Z0-9:.-]*)?(?P<fullpath>/ipfs/(?P<rootcid>[a-zA-Z0-9]{46,59})\/?(?P<subpath>[a-zA-Z0-9<>\"\*:;,\\\?\!\%&=@$~\/\s\.\-\_\'\\\+\(\)]{1,1024})?)\#?(?P<fragment>[a-zA-Z0-9\-\+\_\.\/]{1,256})?$', # noqa
    flags=re.MULTILINE)

ipfsCidRe = re.compile(
    r'^(\s*)?(?P<cid>[a-zA-Z0-9]{46,59})$', flags=re.MULTILINE)

ipnsPathRe = re.compile(
    r'^(\s*)?(?:fs:(\/*)|ipfs:|dweb:(\/*)?|https?://[a-zA-Z0-9:.-]*)?(?P<fullpath>/ipns/([a-zA-Z0-9\.\-\_]{1,128})\/?(?P<subpath>[a-zA-Z0-9<>\"\*:;,\\\?\!\%&=@$~\/\s\.\-\_\'\\\+\(\)]{1,1024})?)\#?(?P<fragment>[a-zA-Z0-9\+\-\_\.\/]{1,256})?$',  # noqa
    flags=re.MULTILINE)


class IPFSPath:
    maxLength = 2048

    def __init__(self, input):
        if not isinstance(input, str):
            raise ValueError('path should be a string')

        self._enableBase32 = False
        self._input = input
        self._rscPath = None
        self._subPath = None
        self._fragment = None
        self._resolvedMultihash = None
        self._valid = self.__analyze()

    @property
    def input(self):
        return self._input

    @property
    def valid(self):
        return self._valid

    @property
    def resolvedMultihash(self):
        return self._resolvedMultihash

    @property
    def isIpfs(self):
        return self.valid is True and isIpfsPath(self.path)

    @property
    def isIpfsRoot(self):
        return self.isIpfs is True and self.subPath is None

    @property
    def isIpns(self):
        return self.valid is True and isIpnsPath(self.path)

    @property
    def isIpnsRoot(self):
        return self.isIpns and self.subPath is None

    @property
    def fragment(self):
        # Return the fragment if there's any
        return self._fragment

    @fragment.setter
    def fragment(self, frag):
        self._fragment = frag

    @property
    def path(self):
        # Return the object path (without fragment)
        return self.objPath

    @property
    def basename(self):
        if self.valid:
            return os.path.basename(self.objPath)

    @property
    def objPath(self):
        # Return the object path (without fragment)
        return self._rscPath

    @property
    def subPath(self):
        # Return the sub path
        return self._subPath

    @property
    def fullPath(self):
        if isinstance(self.fragment, str):
            return self._rscPath + '#' + self.fragment
        else:
            return self._rscPath

    @property
    def dwebUrl(self):
        return 'dweb:{}'.format(self.fullPath)

    @property
    def dwebQtUrl(self):
        return QUrl(self.dwebUrl)

    def __analyze(self):
        """
        Analyze the path and returns a boolean (valid or not)

        :rtype bool
        """

        if len(self.input) > self.maxLength:
            return False

        ma = ipfsRegSearchPath(self.input)

        if ma:
            gdict = ma.groupdict()
            if 'rootcid' not in gdict or 'fullpath' not in gdict:
                return False

            cid = ma.group('rootcid')
            if not cidValid(cid):
                return False

            self._rscPath = ma.group('fullpath').rstrip('/')
            self._fragment = gdict.get('fragment')
            self._subPath = gdict.get('subpath')
            return True

        ma = ipnsRegSearchPath(self.input)
        if ma:
            gdict = ma.groupdict()
            self._rscPath = ma.group('fullpath').rstrip('/')
            self._fragment = gdict.get('fragment')
            self._subPath = gdict.get('subpath')
            return True

        ma = ipfsRegSearchCid(self.input)
        if ma:
            cidStr = ma.group('cid')
            if not cidValid(cidStr):
                return

            cidObject = getCID(cidStr)
            if cidObject.version == 1 and self._enableBase32:
                cidB32 = cidConvertBase32(cidStr)
                if cidB32:
                    path = joinIpfs(cidB32)
            else:
                path = joinIpfs(cidStr)

            self._rscPath = path
            return True

        return False

    def child(self, path):
        if not isinstance(path, str):
            raise ValueError('Need string')

        return IPFSPath(os.path.join(self.objPath, path))

    async def resolve(self, ipfsop):
        """
        Resolve this object path to a multihash
        """

        timeout = 15
        if self.resolvedMultihash:
            # Return cached value
            return self.resolvedMultihash

        haveResolve = await ipfsop.hasCommand('resolve')

        try:
            if haveResolve:
                # Use /api/vx/resolve as the preferred resolve strategy

                resolved = await ipfsop.resolve(self.objPath, timeout=timeout)
                if resolved and isIpfsPath(resolved):
                    resolved = stripIpfs(resolved)

                    if cidValid(resolved):
                        self._resolvedMultihash = resolved
                        return self.resolvedMultihash

            # Use object stat
            info = StatInfo(await ipfsop.objStat(
                self.objPath, timeout=timeout))

            if info.valid and cidValid(info.multihash):
                self._resolvedMultihash = info.multihash
                return self.resolvedMultihash
        except aioipfs.APIError:
            log.debug('Error resolving {0}'.format(self.objPath))
            return None

    def __str__(self):
        return self.fullPath if self.valid else 'Invalid path: {}'.format(
            self.input)

    def __eq__(self, other):
        if isinstance(other, IPFSPath) and other.valid and self.valid:
            return self.fullPath == other.fullPath
        return False

    def __repr__(self):
        return '{path} (fragment: {frag})'.format(
            path=self.fullPath,
            frag=self.fragment if self.fragment else 'No fragment')


def ipfsRegSearchPath(text):
    return ipfsPathRe.match(text)


def ipfsRegSearchCid(text):
    return ipfsCidRe.match(text)


def ipnsRegSearchPath(text):
    return ipnsPathRe.match(text)


def ipfsPathExtract(text):
    ma = ipfsRegSearchPath(text)
    if ma:
        return ma.group('fullpath')

    ma = ipnsRegSearchPath(text)
    if ma:
        return ma.group('fullpath')

    if ipfsRegSearchCid(text):
        return joinIpfs(text)
