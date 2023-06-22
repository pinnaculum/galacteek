import asyncio
import shutil
import functools
import re
import binascii
import struct
import platform
import os
import os.path

import aioipfs

from galacteek import log
from galacteek.ipfs import ipfsOpFn
from galacteek.ipfs.ipfsops import APIErrorDecoder
from galacteek.core.asynclib import asyncReadFile
from galacteek.core import inPyInstaller
from galacteek.core import pyInstallerBundleFolder


iMagic = None


try:
    import magic
except ImportError:
    haveMagic = False
else:
    haveMagic = True


# MIME types outside of the 'text' MIME category that we treat as text
MTYPES_SUPPL_TEXT = (
    'application/x-csh',
    'application/x-sh',
    'application/xml',
    'application/x-tex',
    'application/x-latex',
    'application/javascript',
    'application/json'
)


class MimeDecodeError(Exception):
    pass


def isDirMimeType(mType):
    return mType == 'application/x-directory' or mType == 'inode/directory'


def isTextMimeType(mimeType):
    mimeCategory = getMimeCategory(mimeType)
    return (mimeCategory == 'text' and mimeType != 'text/html') or \
        mimeType in MTYPES_SUPPL_TEXT


def getMimeCategory(mType):
    if isinstance(mType, str):
        splitted = mType.split('/')
        if len(splitted) == 2:
            return splitted[0]


# Bit improvised this one
mimeReg = re.compile(
    r'^(?P<category>[a-zA-Z\-]+)\/(?P<subtype>[a-zA-Z0-9\-\+\.\_]+)'
    r'\;?\s*(?P<params>[\=\-a-zA-Z0-9]*)?$')


class MIMEType(object):
    """
    Represents a MIME type
    """

    def __init__(self, mTypeText):
        if not isinstance(mTypeText, str):
            raise ValueError('Expecting a string')

        self._mType = mTypeText
        self._matched = mimeReg.match(mTypeText)

    @property
    def type(self):
        return self._mType

    @property
    def category(self):
        if self.valid:
            comps = self._decompose()
            return comps[0]

        return 'unknown'

    @property
    def valid(self):
        return self._matched is not None

    def _decompose(self):
        # Decompose the MIME type in: category, subtype, optional params
        ma = self._matched
        if ma:
            return ma.group('category'), ma.group(
                'subtype'), ma.group('params')

    @property
    def isText(self):
        return (self.category == 'text' and self.type != 'text/html') or \
            self.type in MTYPES_SUPPL_TEXT

    @property
    def isHtml(self):
        return self.type == 'text/html' or self.type == 'application/xhtml+xml'

    @property
    def isDir(self):
        return self.type == 'application/x-directory' or \
            self.type == 'inode/directory'

    @property
    def isApplication(self):
        return self.category == 'application'

    @property
    def isAudio(self):
        return self.category == 'audio'

    @property
    def isVideo(self):
        return self.category == 'video'

    @property
    def isModel(self):
        return self.category == 'model'

    @property
    def isImage(self):
        return self.category == 'image'

    @property
    def isAnimation(self):
        return self.type in ['image/gif', 'image/webp', 'video/x-mng']

    @property
    def isChemical(self):
        return self.category == 'chemical'

    @property
    def isMessage(self):
        return self.category == 'message'

    @property
    def isMultipart(self):
        return self.category == 'multipart'

    @property
    def isPdf(self):
        return self.type == 'application/pdf'

    @property
    def isWasm(self):
        return self.type == 'application/wasm'

    @property
    def isAtomFeed(self):
        return self.type == 'application/atom+xml'

    @property
    def isBitTorrent(self):
        return self.type == 'application/x-bittorrent'

    @property
    def isTurtle(self):
        return self.type == 'text/turtle'

    @property
    def isJson(self):
        return self.type == 'application/json'

    @property
    def isYaml(self):
        return self.type in ['application/yaml', 'text/yaml']

    def __str__(self):
        return self.type

    def __eq__(self, value):
        if isinstance(value, str):
            return self.type == value
        elif self.__class__ == value.__class__:
            return self.type == value.type


mimeTypeDagPb = MIMEType('ipfs/dag-pb')
mimeTypeDagUnknown = MIMEType('ipfs/dag-unknown')
mimeTypeWasm = MIMEType('application/wasm')

# gpub: e-book containing text files in the "text/gemini" format
mimeTypeGpub = MIMEType('application/gpub+zip')


def magicInstance():
    global iMagic

    if iMagic is None:
        dbPath = os.environ.get('GALACTEEK_MAGIC_DBPATH')
        sys = platform.system()

        if sys in ['Darwin', 'Windows']:
            if inPyInstaller():
                dbPath = str(pyInstallerBundleFolder().joinpath('magic.mgc'))

        if dbPath and os.path.isfile(dbPath):
            log.debug(f'Using magic DB from path: {dbPath}')

            iMagic = magic.Magic(mime=True, magic_file=dbPath)
        else:
            iMagic = magic.Magic(mime=True)

    return iMagic


def mimeTypeProcess(mTypeText, buff, info=None) -> MIMEType:
    if mTypeText == 'text/xml':
        # If it's an XML, check if it's an Atom feed from the buffer
        # Can't call feedparser here cause we only got a partial buffer
        atomized = re.search('<feed xmlns="http://www.w3.org/[0-9]+/Atom".*>',
                             buff.decode())
        if atomized:
            return MIMEType('application/atom+xml')
    elif mTypeText == 'application/octet-stream':
        # Check for WASM magic number
        wasmMagic = binascii.unhexlify(b'0061736d')

        if buff[0:4] == wasmMagic:
            version = struct.unpack('<I', buff[4:8])[0]
            log.warning('Detected WASM binary, version {}'.format(version))
            return mimeTypeWasm

    return MIMEType(mTypeText)


def detectMimeTypeFromBufferSync(buff: bytes) -> MIMEType:
    m = magicInstance()
    mime = m.from_buffer(buff)

    if isinstance(mime, str):
        return mimeTypeProcess(mime, buff)


async def detectMimeTypeFromBuffer(buff: bytes) -> MIMEType:
    """
    Guess the MIME type from a bytes buffer, using either libmagic or file(1)

    Returns a MIMEType object

    :param bytes buff: buffer data
    :rtype: MIMEType
    """

    infoString = None
    if haveMagic:
        # Use libmagic
        # Run it in an asyncio executor
        loop = asyncio.get_event_loop()

        try:
            m = magicInstance()
            mime = await loop.run_in_executor(
                None, functools.partial(m.from_buffer, buff))
        except Exception as err:
            log.debug(f'Error running magic: {err}')
            return None
        else:
            if isinstance(mime, str):
                return mimeTypeProcess(mime, buff, info=infoString)
    elif shutil.which('file'):
        # Libmagic not available, go with good'ol file

        try:
            proc = await asyncio.create_subprocess_shell(
                'file --mime-type -',
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate(buff)

            out = stdout.decode().strip()
            spl = out.split(':')
        except:
            return None
        else:
            if len(spl) == 2 and spl[0] == '/dev/stdin':
                return mimeTypeProcess(spl[1].strip(), buff)
    else:
        raise MimeDecodeError('No MIME detection method available')


async def detectMimeTypeFromFile(filePath, bufferSize=131070):
    buff = await asyncReadFile(filePath, size=bufferSize)

    if buff:
        return await detectMimeTypeFromBuffer(buff)


@ipfsOpFn
async def detectMimeType(ipfsop, rscPath, bufferSize=131070, timeout=15):
    """
    Returns the MIME type of a given IPFS resource
    Uses either python-magic if available, or runs the 'file' command

    Special cases:
        * for directories it will return 'inode/directory'
        * for IPFS DAG nodes it will return 'ipfs/dag-pb'

    A chunk of the file is read and used to determine its MIME type

    Returns a MIMEType object

    :param ipfsop: IPFS operator instance
    :param str rscPath: IPFS CID/path
    :param int bufferSize: buffer size in bytes
    :param int timeout: operation timeout (in seconds)
    :rtype: MIMEType
    """
    try:
        buff = await ipfsop.catObject(
            rscPath, length=bufferSize, timeout=timeout)
    except aioipfs.APIError as err:
        dec = APIErrorDecoder(err.message)

        if dec.errIsDirectory():
            return MIMEType('inode/directory')
        elif dec.errUnknownNode():
            # Unknown kind of node, let the caller analyze the DAG
            return mimeTypeDagUnknown
    else:
        if not buff:
            return None

        return await detectMimeTypeFromBuffer(buff)
