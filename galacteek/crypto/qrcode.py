import io

from PIL import Image

from galacteek import log
from galacteek.ipfs.cidhelpers import ipfsPathExtract


try:
    from pyzbar.pyzbar import decode as zbar_decode
    from pyzbar import zbar_library
    zbar_library.load()
except ImportError:
    haveZbar = False
else:
    haveZbar = True


try:
    from qreader.decoder import QRDecoder
    from qreader.scanner import ImageScanner
except ImportError:
    haveQReader = False
else:
    haveQReader = True


class ImageReader:
    def _getImage(self, data):
        try:
            image = Image.open(io.BytesIO(data))
        except:
            log.debug('Cannot open image with Pillow')
            return None
        else:
            return image


class ZbarIPFSQrDecoder(ImageReader):
    def decode(self, data):
        if not isinstance(data, bytes):
            raise Exception('Need bytes')

        try:
            image = self._getImage(data)

            if image is None:
                return

            objects = zbar_decode(image)

            urls = []
            for obj in objects:
                if not isinstance(obj.data, bytes):
                    continue
                try:
                    decoded = obj.data.decode()
                except BaseException:
                    continue

                if len(decoded) not in range(1, 1024):
                    continue

                path = ipfsPathExtract(decoded)
                if path and path not in urls:
                    urls.append(path)

            if len(urls) > 0:  # don't return empty list
                return urls
        except Exception:
            return None


class QReaderIPFSQrDecoder(ImageReader):
    """
    Decodes IPFS QR codes with the qreader library
    """

    def decode(self, data):
        """
        Try to decode all the QR codes with IPFS addresses contained
        in an image. Returns a list of IPFS paths, or None if no URL
        was found.

        :param bytes data: Raw image data
        :rtype: list
        """
        if not isinstance(data, bytes):
            raise Exception('Need bytes')

        try:
            image = self._getImage(data)

            if image is None:
                return

            imgScanner = ImageScanner(image)
            results = QRDecoder(imgScanner).get_all()

            urls = []
            for obj in results:
                if not isinstance(obj, str):
                    continue
                if len(obj) not in range(1, 1024):
                    continue

                path = ipfsPathExtract(obj)
                if path and path not in urls:
                    urls.append(path)

            if len(urls) > 0:  # don't return empty list
                return urls
        except Exception:
            return None


def IPFSQrDecoder():
    # Returns a suitable QR decoder depending on the available libs
    if haveZbar:
        log.debug('Using pyzbar decoder')
        return ZbarIPFSQrDecoder()
    elif haveQReader:
        log.debug('Using qreader decoder')
        return QReaderIPFSQrDecoder()
    else:
        return None
