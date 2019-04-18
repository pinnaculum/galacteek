import asyncio
import shutil
import functools

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


async def detectMimeTypeFromBuffer(buff):
    """
    Guess the MIME type from a bytes buffer, using either libmagic or file(1)

    :param bytes buff: buffer data
    :rtype: str
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
            return mime
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
                return spl[1].strip()
    else:
        raise MimeDecodeError('No MIME detection method available')


@ipfsOpFn
async def detectMimeType(ipfsop, rscPath, bufferSize=512, timeout=8):
    """
    Returns the MIME type of a given IPFS resource
    Uses either python-magic if available, or runs the 'file' command

    A chunk of the file is read and used to determine its MIME type

    :param ipfsop: IPFS operator instance
    :param str rscPath: IPFS CID/path
    :param int bufferSize: buffer size in bytes
    :param int timeout: operation timeout (in seconds)
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
            return 'inode/directory'
    else:
        if not buff:
            return None

        return await detectMimeTypeFromBuffer(buff)
