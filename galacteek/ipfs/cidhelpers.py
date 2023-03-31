import re
import os
from typing import Union
import aioipfs

from rdflib import URIRef
from urllib.parse import quote
from urllib.parse import unquote
from yarl import URL

from PyQt5.QtCore import QUrl

from galacteek import log
from galacteek.core.ps import hubLdPublish
from galacteek.core.ps import key42
from galacteek.ipfs.paths import posixIpfsPath
from galacteek.ipfs.cid import CIDv1
from galacteek.ipfs.cid import CIDv0
from galacteek.ipfs.cid import make_cid
from galacteek.ipfs.cid import BaseCID
from galacteek.ipfs.stat import StatInfo

import multihash
import functools


def normp(path):
    sep = '/'
    final = path.endswith(sep)
    normed = posixIpfsPath.normpath(path)

    if final:
        return normed + sep

    return normed


def normpPreserve(path, preserveTrailing=True):
    """
    Like os.path.normpath but preserves trailing slash by default
    and couldn't care less about normalizing ..
    """
    path = os.fspath(path)

    sep = '/'
    empty = ''
    dot = '.'

    if path == empty:
        return dot

    initial_slashes = path.startswith(sep)
    final_slashes = path.endswith(sep)

    comps = path.split(sep)
    new_comps = []
    for comp in comps:
        if comp in (empty, dot):
            continue
        new_comps.append(comp)
    comps = new_comps
    path = sep.join(comps)
    if initial_slashes:
        path = sep + path
    if final_slashes and preserveTrailing:
        path = path + sep
    return path or dot


def joinIpfs(path):
    if isinstance(path, str):
        return posixIpfsPath.join('/ipfs/', path)


def joinIpns(path):
    if isinstance(path, str):
        return posixIpfsPath.join('/ipns/', path)


def stripIpfs(path):
    if isinstance(path, str):
        return re.sub('^/ipfs/', '', path)


def stripIpns(path):
    if isinstance(path, str):
        return re.sub('^/ipns/', '', path)


def isIpfsPath(path):
    if isinstance(path, str):
        return ipfsRegSearchPath(path) is not None


def isIpnsPath(path):
    if isinstance(path, str):
        return ipnsRegSearchPath(path) is not None


def shortCidRepr(cid):
    cidStr = str(cid)
    if cid.version == 0:
        return '... {0}'.format(cidStr[3 * int(len(cidStr) / 5):])
    else:
        b32Cid = cidConvertBase32(cidStr)
        return '... {0}'.format(b32Cid[4 * int(len(b32Cid) / 5):])


def shortPathRepr(path):
    if isIpfsPath(path) or isIpnsPath(path):
        basename = posixIpfsPath.basename(path)
        if cidValid(basename):
            cid = getCID(basename)
            return shortCidRepr(cid)
        else:
            return basename[0:64]
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


def getCID(cidStr):
    try:
        return make_cid(cidStr)
    except BaseException:
        return None


def cidUpgrade(cid):
    """
    Converts a cid.CIDv0 instance to a cid.CIDv1
    """

    try:
        if issubclass(cid.__class__, BaseCID) and cid.version == 0:
            return cid.to_v1()
    except Exception:
        return None


def cidDowngrade(cid: CIDv1):
    """
    Converts a cid.CIDv1 instance to a cid.CIDv0
    """

    try:
        if issubclass(cid.__class__, BaseCID) and cid.version == 1:
            return cid.to_v0()
    except Exception:
        return None


def cidConvertBase32(cid: str):
    """
    Convert a base58-encoded CID to a base32 string

    If it's a CIDv0, it's upgraded to CIDv1 first

    :param str cid: The cid string
    :rtype: str
    """

    cid = getCID(cid)
    if not cid:
        return None

    if cid.version == 0:
        if not cidValid(cid):
            return None

        cid = cidUpgrade(cid)
        if not cid:
            log.debug('Impossible to convert CIDv0: {}'.format(cid))
            return None

    return cid.encode('base32').decode()


def ipnsKeyCidV1(ipnsKey: str, multicodec='libp2p-key'):
    """
    Converts a base58 IPNS key to a CIDv1 in base36 with the
    'libp2p-key' multicodec. If it's already a CIDv1
    (new IPNS keys in base36) return it in base36.

    :rtype: str
    """

    cid = getCID(ipnsKey)
    if not cid:
        return None

    if cid.version == 1 and cid.codec == 'libp2p-key':
        # Already CIDv1 using 'libp2p-key' codec
        # Return it encoded in base36
        return cid.encode('base36').decode()

    # Create the CIDv1 with the requested multicodec
    cidV1 = CIDv1(multicodec, cid.multihash)

    return cidV1.encode('base36').decode()


@functools.lru_cache(maxsize=128)
def peerIdReencode(peerId: str,
                   base: str = 'base36',
                   multicodec: str = 'libp2p-key'):
    """
    Encode a PeerId to a specific base
    """

    cid = getCID(peerId)
    if not cid:
        return None

    if base in ['base32', 'base36']:
        cidV1 = CIDv1(multicodec, cid.multihash)
        return cidV1.encode(base).decode()
    elif base in ['base58']:
        # asssume CIDv0
        cidV0 = CIDv0(cid.multihash)
        return str(cidV0)

    return None


def peerIdBase32(peerId: str):
    """
    Convert any PeerId to a CIDv1 (base32)
    """
    return peerIdReencode(peerId, base='base32')


def peerIdBase36(peerId: str):
    """
    Convert any PeerId to a CIDv1 (base36)
    """
    return peerIdReencode(peerId, base='base36')


def peerIdBase58(peerId: str):
    """
    Convert any PeerId to a CIDv0 (base58)
    """
    return peerIdReencode(peerId, base='base58')


def cidValid(cid):
    """
    Check if the passed argument is a valid IPFS CID

    :param cid: the CID to validate, can be a string or a BaseCID
    :return: if the value is a valid CID or not
    :rtype: bool
    """

    if cid is None:
        return False

    if isinstance(cid, str):
        c = getCID(cid)
    elif issubclass(cid.__class__, BaseCID):
        c = cid
    else:
        return False

    if c is None:
        return False
    if c.version in [0, 1]:
        # Ensure that we can decode the multihash
        try:  # can raise ValueError
            if multihash.decode(c.multihash):
                return True
        except BaseException:
            return False
    return False


domainReStr = r'([A-Za-z0-9]\.|[A-Za-z0-9][A-Za-z0-9-]{0,61}[A-Za-z0-9]\.){1,3}[A-Za-z]{2,6}'  # noqa

domainRe = re.compile(rf'^{domainReStr}$')


def domainValid(domain):
    return domainRe.match(domain)


# Regexps

pathChars = r'\w|<>"\/:;,!\*%&\?=@\$~/\s\.\-_\\\'()\+\[\]'

query = r'(?P<query>[\w?=&:;+]*)?'

fragment = r'#?(?P<fragment>[\w_\.\-\+,;:=/?]{1,256})?$'


ipfsLinkRe = re.compile(r'^(/(ipfs|ipns)/[' + pathChars + ']{1,1024}$)')


ipfsPathRe = re.compile(
    r'(?:fs:|dweb:|dwebgw:|https?://[\w:.-]+)?(?P<fullpath>(/ipfs/)?(?P<rootcid>[a-zA-Z0-9]{46,113})/?(?P<subpath>[' + pathChars + ']{1,1024})?)' + query + fragment,  # noqa
    flags=re.UNICODE)


# For subdomain gateway URLs
# https://docs.ipfs.tech/how-to/address-ipfs-on-web/#subdomain-gateway
# string length regex range for the root CID doesn't matter that much as
# it's decoded by IPFSPath and must be a valid CID

ipfsSubdomainUrlRe = re.compile(
    r'\s*https?://(?P<rootcid>[a-z0-9]{46,113})\.(?P<gwscheme>(ipfs|ipns))\.' +
    domainReStr +
    r':?(?P<httpport>[\d]+)?' +
    r'(?P<subpath>/[' +
    pathChars +
    ']{1,1024})?' +
    query +
    fragment,
    flags=re.UNICODE
)


# For ipfs://<cid-base32>
ipfsPathDedRe = re.compile(
    r'^(\s*)?(?:ipfs://)(?P<fullpath>(?P<rootcid>[a-z2-7]{59,113})/?(?P<subpath>[' + pathChars + ']{1,1024})?)' + query + fragment,  # noqa
    flags=re.UNICODE)

# For rewriting (unlawful) ipfs://<cidv0> or ipfs://<cidv1-base58> to base32
ipfsPathDedRe58 = re.compile(
    r'^(\s*)?(?:ipfs://)(?P<fullpath>(?P<rootcid>[a-zA-Z0-9]{46,113})/?(?P<subpath>[' + pathChars + ']{1,1024})?)' + query + fragment,  # noqa
    flags=re.UNICODE)

# For rewriting (unlawful) ipfs+http://<cidv0>
ipfsHttpPathRe = re.compile(
    r'^(\s*)?(?:ipfs\+http://)((?P<username>[\w\-\.]+)@)?(?P<fullpath>(?P<peerid>[a-zA-Z0-9]{1,62})/?(?P<subpath>[' + pathChars + ']{1,1024})?)' + query + fragment,  # noqa
    flags=re.UNICODE)

ipnsPathDedRe = re.compile(
    r'^(\s*)?(?:(ipns|ipfs)://)(?P<fullpath>(?P<fqdn>[\w.-]+)/?(?P<subpath>[' + pathChars + ']{1,1024})?)' + query + fragment,  # noqa
    flags=re.UNICODE)

ipfsCidRe = re.compile(
    r'^(\s*)?(?P<cid>[a-zA-Z0-9]{46,59})$')

ipfsCid32Re = re.compile(
    r'^(\s*)?(?P<cid>[a-z2-7]{59,113})$')

ipnsKeyRe = re.compile(
    r'^(?P<key>(Qm[\w]{44}))$')

ipnsPathRe = re.compile(
    r'(?:fs:|dweb:|dwebgw:|https?://[\w:.-]+)?(?P<fullpath>/ipns/(?P<fqdn>[\w\.-]+)/?(?P<subpath>[' + pathChars + ']{1,1024})?)' + query + fragment,  # noqa
    flags=re.UNICODE)


ipfsMdMagic = r'(?P<linkname>[\w]+)?(?P<a>#?%?!?@{1,3})'

# Used by markdown extension
ipfsPathMagicRe = re.compile(ipfsMdMagic + ipfsPathRe.pattern,
                             flags=re.UNICODE)
ipnsPathMagicRe = re.compile(ipfsMdMagic + ipnsPathRe.pattern,
                             flags=re.UNICODE)


class IPFSPath:
    maxLength = 1024

    def __init__(self, input, autoCidConv=False, enableBase32=True):
        self._valid = False
        self._enableBase32 = enableBase32
        self._autoCidConv = autoCidConv
        self._rootCid = None
        self._rootCidV = None
        self._rootCidUseB32 = False
        self._input = input
        self._rscPath = None
        self._subPath = None
        self._fragment = None
        self._scheme = None
        self._resolvedCid = None
        self._ipnsId = None
        self._query = None

        self._valid = self.__analyze()

    @property
    def autoCidConv(self):
        return self._autoCidConv

    @property
    def input(self):
        return self._input

    @property
    def valid(self):
        return self._valid

    @property
    def scheme(self):
        return self._scheme

    @property
    def query(self):
        return self._query

    @property
    def ipnsId(self):
        return self._ipnsId

    @property
    def ipnsFqdn(self):
        if domainValid(self.ipnsId):
            return self.ipnsId

    @property
    def ipnsKey(self):
        if not self.ipnsFqdn:
            return self.ipnsId

    @property
    def resolvedCid(self):
        return self._resolvedCid

    @property
    def rootCidV(self):
        return self._rootCidV

    @property
    def rootCid(self):
        return self._rootCid

    @property
    def rootCidRepr(self):
        if self.rootCidUseB32:
            return self._rootCid.encode('base32').decode()
        else:
            return str(self._rootCid)

    @property
    def rootCidUseB32(self):
        return self._rootCidUseB32

    @property
    def isIpfs(self):
        return self.valid is True and self.scheme == 'ipfs'

    @property
    def isRoot(self):
        return self.isIpfsRoot or self.isIpnsRoot

    @property
    def isIpfsRoot(self):
        return self.isIpfs is True and self.subPath is None

    @property
    def isIpns(self):
        return self.valid is True and self.scheme == 'ipns'

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
    def objPathShort(self):
        # Object path (shortened)
        return shortPathRepr(self.objPath)

    @property
    def basename(self):
        if self.valid:
            return posixIpfsPath.basename(self.objPath.rstrip('/'))

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
        return '{scheme}:{path}'.format(
            scheme='dweb',
            path=self.fullPath
        )

    @property
    def publicGwUrl(self):
        return 'https://ipfs.io{path}'.format(
            path=self.fullPath
        )

    @property
    def ipfsUrl(self):
        if self.isIpfs and self.rootCidUseB32:
            # ipfs://
            return '{scheme}://{path}'.format(
                scheme=self.scheme,
                path=stripIpfs(self.fullPath)
            )
        elif self.isIpns:
            if domainValid(self._ipnsId):
                return '{scheme}://{path}'.format(
                    scheme='ipns',
                    path=stripIpns(self.fullPath)
                )
            else:
                return '{scheme}://{path}'.format(
                    scheme=self.scheme,
                    path=stripIpns(self.fullPath)
                )
        else:
            return self.dwebUrl

    @property
    def ipfsUrlEncoded(self):
        if self.isIpfs and self.rootCidUseB32:
            # ipfs://
            return '{scheme}://{path}'.format(
                scheme=self.scheme,
                path=quote(stripIpfs(self.fullPath))
            )
        elif self.isIpns:
            if domainValid(self._ipnsId):
                return '{scheme}://{path}'.format(
                    scheme='ipns',
                    path=quote(stripIpns(self.fullPath))
                )
            else:
                return '{scheme}://{path}'.format(
                    scheme=self.scheme,
                    path=quote(stripIpns(self.fullPath))
                )
        else:
            return self.dwebUrl

    @property
    def ipfsUriRef(self):
        """
        Returns an rdflib URIRef for this object

        One issue is that when inserted into a graph, rdflib seems
        to add a trailing slash.
        If it's a root CID we append a slash to prevent mismatch.
        """

        if self.isRoot:
            return URIRef(self.ipfsUrlEncoded + '/')
        else:
            return URIRef(self.ipfsUrlEncoded)

    @property
    def rPrefsUriRef(self):
        """
        Resource Preferences URI Reference for this object
        """

        return URIRef(f'{self.ipfsUriRef}#prefs')

    @property
    def dwebQtUrl(self):
        return QUrl(self.dwebUrl)

    @property
    def asQtUrl(self):
        return QUrl(self.ipfsUrl)

    def gwUrlForConnParams(self, params):
        return f'http://{params.host}:{params.gatewayPort}{self.fullPath}'

    def publicUrlForGateway(self, gatewayUrl: URL) -> URL:
        """
        Return the URL of this object served from a specific IPFS
        HTTP gateway.

        :rtype: URL
        """
        return gatewayUrl.with_path(self.fullPath)

    @staticmethod
    def fromUriRef(uri: Union[URIRef, str]):
        ref = uri if isinstance(uri, URIRef) else URIRef(uri)
        return IPFSPath(unquote(str(ref)))

    def __analyze(self):
        """
        Analyze the path and returns a boolean (valid or not)

        :rtype bool
        """

        if not isinstance(self.input, str):
            return False

        self._input = self._input.strip()

        if len(self.input) > self.maxLength:
            return False

        ma = ipfsRegSearchSubDomain(self.input)
        if ma:
            gdict = ma.groupdict()
            rCid = gdict.get('rootcid')
            subpath = gdict.get('subpath')
            scheme = gdict.get('gwscheme')

            if scheme == 'ipfs':
                if not self.parseCid(rCid):
                    return False

                if subpath:
                    self._rscPath = self.pathjoin(
                        joinIpfs(self.rootCidRepr),
                        subpath
                    )
                else:
                    self._rscPath = joinIpfs(self.rootCidRepr)
            elif scheme == 'ipns':
                if subpath:
                    self._rscPath = self.pathjoin(
                        joinIpns(rCid),
                        subpath
                    )
                else:
                    self._rscPath = joinIpns(rCid)

                self._ipnsId = rCid

            self._subPath = subpath if subpath else '/'
            self._scheme = scheme
            self._query = gdict.get('query')
            self._fragment = gdict.get('fragment')

            self.hubNotify()

            return True

        ma = ipfsDedSearchPath(self.input)
        if ma:
            gdict = ma.groupdict()
            if 'rootcid' not in gdict or 'fullpath' not in gdict:
                return False

            cid = ma.group('rootcid')

            if not self.parseCid(cid):
                return False

            subpath = gdict.get('subpath')

            if subpath:
                self._rscPath = self.pathjoin(
                    joinIpfs(self.rootCidRepr),
                    subpath
                )
            else:
                self._rscPath = joinIpfs(self.rootCidRepr)

            self._query = gdict.get('query')
            self._fragment = gdict.get('fragment')
            self._subPath = subpath
            self._scheme = 'ipfs'

            self.hubNotify()

            return True

        ma = ipfsRegSearchPath(self.input)
        if ma:
            gdict = ma.groupdict()
            if 'rootcid' not in gdict or 'fullpath' not in gdict:
                return False

            cid = ma.group('rootcid')

            if not self.parseCid(cid):
                return False

            subpath = gdict.get('subpath')
            if subpath:
                self._rscPath = self.pathjoin(
                    joinIpfs(self.rootCidRepr),
                    subpath
                )
            else:
                self._rscPath = joinIpfs(self.rootCidRepr)

            self._query = gdict.get('query')
            self._fragment = gdict.get('fragment')
            self._subPath = gdict.get('subpath')
            self._scheme = 'ipfs'

            self.hubNotify()

            return True

        ma = ipnsRegSearchPath(self.input)
        if ma:
            gdict = ma.groupdict()

            subpath = gdict.get('subpath')
            ipnsIdV1 = ipnsKeyCidV1(gdict.get('fqdn'))
            _id = ipnsIdV1 if ipnsIdV1 else gdict.get('fqdn')

            if subpath:
                self._rscPath = self.pathjoin(
                    joinIpns(_id),
                    subpath
                )
            else:
                self._rscPath = joinIpns(_id)

            self._ipnsId = _id
            self._query = gdict.get('query')
            self._fragment = gdict.get('fragment')
            self._subPath = gdict.get('subpath')
            self._scheme = 'ipns'

            self.hubNotify()

            return True

        ma = ipfsRegSearchCid(self.input)
        if ma:
            cidStr = ma.group('cid')

            if not self.parseCid(cidStr):
                return False

            self._rscPath = joinIpfs(self.rootCidRepr)
            self._scheme = 'ipfs'

            self.hubNotify()

            return True

        return False

    def hubNotify(self):
        pass

    def hubRealNotify(self):
        hubLdPublish(
            key42, {
                'type': 'IPFSObjectDetailsEvent',

                'url': self.ipfsUrl,
                'rootCid': self.rootCidRepr,
                'objPath': self.objPath
            }
        )

    def pathjoin(self, path1, path2):
        return posixIpfsPath.join(path1, path2.lstrip('/'))

    def parseCid(self, cidStr):
        if not cidValid(cidStr):
            return False

        self._rootCid = getCID(cidStr)
        if self.rootCid:
            self._rootCidV = self.rootCid.version if \
                self.rootCid.version in range(0, 2) else None
        else:
            return False

        if self._autoCidConv and self.rootCid.version == 0:
            # Automatic V0-to-V1 conversion
            self._rootCid = cidUpgrade(self._rootCid)

        if self.rootCid.version == 1 and self._enableBase32:
            # rootCidRepr will convert it to base32
            self._rootCidUseB32 = True

        return True

    def ipnsIdCompare(self, p):
        return self.ipnsId == p.ipnsId

    def child(self, path, normalize=False):
        if not isinstance(path, str):
            raise ValueError('Need string')

        if self.subPath is None and (path == '..' or path.startswith('../')):
            # Not crossing the /{ipfs,ipns} NS
            return self

        if normalize:
            cPath = normp(path)
            return IPFSPath(normp(
                posixIpfsPath.join(self.objPath, cPath.lstrip('/'))))
        else:
            cPath = normpPreserve(path)
            return IPFSPath(
                posixIpfsPath.join(
                    self.objPath,
                    cPath.lstrip('/')))

    def parent(self):
        return self.child('../', normalize=True)

    def root(self):
        n = self
        while n.valid and n.subPath:
            n = n.parent()

        return n if n.valid else None

    def shortRepr(self):
        if self.isIpfsRoot:
            return shortCidRepr(self._rootCid)

        if self.isIpnsRoot:
            return self.objPath

        if self.isIpfs or self.isIpns:
            basename = self.basename

            if not basename:
                return ''

            if len(basename) > 16:
                return '... {0}'.format(basename[3 * int(len(basename) / 5):])
            elif len(basename) > 24:
                return '... {0}'.format(basename[4 * int(len(basename) / 5):])
            else:
                return basename

    async def resolve(self, ipfsop, noCache=False, timeout=10):
        """
        Resolve this object's path to a CID
        """

        if self.resolvedCid and noCache is False:
            # Return cached value
            return self.resolvedCid

        haveResolve = await ipfsop.hasCommand('resolve')

        try:
            if haveResolve:
                # Use /api/vx/resolve as the preferred resolve strategy

                resolved = await ipfsop.resolve(self.objPath, timeout=timeout)
                if resolved and isIpfsPath(resolved):
                    resolved = stripIpfs(resolved)

                    if cidValid(resolved):
                        self._resolvedCid = resolved
                        return self.resolvedCid

            # Use object stat
            info = StatInfo(await ipfsop.objStat(
                self.objPath, timeout=timeout))

            if info.valid and cidValid(info.cid):
                self._resolvedCid = info.cid
                return self.resolvedCid
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


def ipfsRegSearchPath(text: str):
    return ipfsPathRe.match(text)


def ipfsDedSearchPath(text: str):
    # search for the dedicated ipfs:// scheme
    return ipfsPathDedRe.match(text)


def ipfsRegSearchSubDomain(text: str):
    return ipfsSubdomainUrlRe.match(text)


def ipfsDedSearchPath58(text: str):
    # Like ipfsDedSearchPath() but allows any type of CID (including
    # CIDv0) as root CID. Only used to be able to extract the root CID
    # and replace it with the base32 version
    return ipfsPathDedRe58.match(text)


def ipfsHttpSearch(text: str):
    return ipfsHttpPathRe.match(text)


def ipfsRegSearchCid(text: str):
    return ipfsCidRe.match(text)


def ipfsRegSearchCid32(text: str):
    return ipfsCid32Re.match(text)


def ipnsRegSearchPath(text: str):
    return ipnsPathRe.match(text) or ipnsPathDedRe.match(text)


def ipfsPathExtract(text: str):
    ma = ipfsRegSearchPath(text)
    if ma:
        return ma.group('fullpath')

    ma = ipnsRegSearchPath(text)
    if ma:
        return ma.group('fullpath')

    if ipfsRegSearchCid(text):
        return joinIpfs(text)


def qurlPercentDecode(qurl: QUrl):
    return QUrl(QUrl.fromPercentEncoding(qurl.toEncoded())).toString()
