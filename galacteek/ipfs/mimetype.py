import asyncio
import shutil
import functools
import re

import aioipfs

from galacteek.ipfs import ipfsOpFn


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

    def __str__(self):
        return self.type

    def __eq__(self, value):
        if isinstance(value, str):
            return self.type == value
        elif self.__class__ == value.__class__:
            return self.type == value.type


async def detectMimeTypeFromBuffer(buff):
    """
    Guess the MIME type from a bytes buffer, using either libmagic or file(1)

    Returns a MIMEType object

    :param bytes buff: buffer data
    :rtype: MIMEType
    """
    if haveMagic:
        # Use libmagic
        # Run it in an asyncio executor
        loop = asyncio.get_event_loop()
        try:
            mime = await loop.run_in_executor(
                None, functools.partial(magic.from_buffer, buff, mime=True))
        except Exception:
            return None
        else:
            return MIMEType(mime)
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
                return MIMEType(spl[1].strip())
    else:
        raise MimeDecodeError('No MIME detection method available')


@ipfsOpFn
async def detectMimeType(ipfsop, rscPath, bufferSize=512, timeout=12):
    """
    Returns the MIME type of a given IPFS resource
    Uses either python-magic if available, or runs the 'file' command

    A chunk of the file is read and used to determine its MIME type

    Returns a MIMEType object

    :param ipfsop: IPFS operator instance
    :param str rscPath: IPFS CID/path
    :param int bufferSize: buffer size in bytes
    :param int timeout: operation timeout (in seconds)
    :rtype: MIMEType
    """
    try:
        buff = await ipfsop.waitFor(
            ipfsop.client.cat(rscPath, length=bufferSize), timeout
        )
    except aioipfs.APIError as err:
        if isinstance(err.message, str) and \
                err.message.lower() == 'this dag node is a directory':
            if 0:
                # This could serve later on, right now treat it
                # always as a directory
                async for obj in ipfsop.list(rscPath, resolve_type=False):
                    for entry in obj['Links']:
                        await ipfsop.sleep()
                        if entry['Name'].startswith('index.htm'):
                            return 'text/html'
            return MIMEType('inode/directory')
    else:
        if not buff:
            return None

        return await detectMimeTypeFromBuffer(buff)
