# -*- coding: utf-8 -*-
#
# MIT License
#
# Copyright (c) 2017, Dhruv Baldawa
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

import base58

import multibase

from morphys import ensure_bytes, ensure_unicode

import multicodec


class BaseCID(object):
    __hash__ = object.__hash__

    def __init__(self, version, codec, multihash):
        """
        Creates a new CID object. This class should not be used directly,
        use :py:class:`cid.cid.CIDv0` or :py:class:`cid.cid.CIDv1` instead.


        :param int version: CID version (0 or 1)
        :param str codec: codec to be used for encoding the hash
        :param str multihash: the multihash
        """
        self._version = version
        self._codec = codec
        self._multihash = ensure_bytes(multihash)

    @property
    def version(self):
        """ CID version """
        return self._version

    @property
    def codec(self):
        """ CID codec """
        return self._codec

    @property
    def multihash(self):
        """ CID multihash """
        return self._multihash

    @property
    def buffer(self):
        raise NotImplementedError

    def encode(self, *args, **kwargs):
        raise NotImplementedError

    def __repr__(self):
        def truncate(s, length):
            return s[:length] + b'..' if len(s) > length else s

        truncate_length = 20
        return '{class_}(version={version}, codec={codec}, multihash={multihash})'.format(  # noqa
            class_=self.__class__.__name__,
            version=self._version,
            codec=self._codec,
            multihash=truncate(
                self._multihash,
                truncate_length),
        )

    def __str__(self):
        return ensure_unicode(self.encode())

    def __eq__(self, other):
        return (
            self.version == other.version) and (
            self.codec == other.codec) and (
            self.multihash == other.multihash)


class CIDv0(BaseCID):
    """ CID version 0 object """
    CODEC = 'dag-pb'

    def __init__(self, multihash):
        """
        :param bytes multihash: multihash for the CID
        """
        super(CIDv0, self).__init__(0, self.CODEC, multihash)

    @property
    def buffer(self):
        """
        The raw representation that will be encoded.

        :return: the multihash
        :rtype: bytes
        """
        return self.multihash

    def encode(self):
        """
        base58-encoded buffer

        :return: encoded representation or CID
        :rtype: bytes
        """
        return ensure_bytes(base58.b58encode(self.buffer))

    def to_v1(self):
        """
        Get an equivalent :py:class:`cid.CIDv1` object.

        :return: :py:class:`cid.CIDv1` object
        :rtype: :py:class:`cid.CIDv1`
        """
        return CIDv1(self.CODEC, self.multihash)


class CIDv1(BaseCID):
    """ CID version 1 object """

    def __init__(self, codec, multihash):
        super(CIDv1, self).__init__(1, codec, multihash)

    @property
    def buffer(self):
        """
        The raw representation of the CID

        :return: raw representation of the CID
        :rtype: bytes
        """
        return b''.join(
            [bytes([self.version]), multicodec.add_prefix(self.codec,
                                                          self.multihash)])

    def encode(self, encoding='base58btc'):
        """
        Encoded version of the raw representation

        :param str encoding: the encoding to use to encode the raw
            representation, should be supported by ``py-multibase``
        :return: encoded raw representation with the given encoding
        :rtype: bytes
        """
        return multibase.encode(encoding, self.buffer)

    def to_v0(self):
        """
        Get an equivalent :py:class:`cid.CIDv0` object.

        :return: :py:class:`cid.CIDv0` object
        :rtype: :py:class:`cid.CIDv0`
        :raise ValueError: if the codec is not 'dag-pb'
        """
        if self.codec != CIDv0.CODEC:
            raise ValueError(
                'CIDv1 can only be converted for codec {}'.format(
                    CIDv0.CODEC))

        return CIDv0(self.multihash)


def make_cid(*args):
    """
    Creates a :py:class:`cid.CIDv0` or :py:class:`cid.CIDv1` object based
    on the given parameters

    The function supports the following signatures:

            make_cid(<base58 encoded multihash CID>) -> CIDv0

            make_cid(<multihash CID>) -> CIDv0

            make_cid(<multibase encoded multihash CID>) -> CIDv1

            make_cid(<version>, <codec>, <multihash>) -> CIDv1

    :param args:
        - base58-encoded multihash (str or bytes)
        - multihash (str or bytes)
        - multibase-encoded multihash (str or bytes)
        - version:int, codec(str), multihash(str or bytes)
    :returns: the respective CID object
    :rtype: :py:class:`cid.CIDv0` or :py:class:`cid.CIDv1`
    :raises ValueError: if the number of arguments is not 1 or 3
    :raises ValueError: if the only argument passed is not a ``str`` or a
        ``byte``
    :raises ValueError: if 3 arguments are passed and version is not 0 or 1
    :raises ValueError: if 3 arguments are passed and the ``codec`` is not
        supported by ``multicodec``
    :raises ValueError: if 3 arguments are passed and the ``multihash`` is not
        ``str`` or ``byte``
    :raises ValueError: if 3 arguments are passed with version 0 and codec is
        not *dag-pb*
    """
    if len(args) == 1:
        data = args[0]
        if isinstance(data, str):
            return from_string(data)
        elif isinstance(data, bytes):
            return from_bytes(data)
        else:
            raise ValueError(
                'invalid argument passed, expected: str or byte, found: {}'.format(  # noqa
                    type(data)))

    elif len(args) == 3:
        version, codec, multihash = args
        if version not in (0, 1):
            raise ValueError(
                'version should be 0 or 1, {} was provided'.format(version))
        if not multicodec.is_codec(codec):
            raise ValueError(
                'invalid codec {} provided, please check'.format(codec))
        if not (isinstance(multihash, str) or isinstance(multihash, bytes)):
            raise ValueError(
                'invalid type for multihash provided, should be str or bytes')

        if version == 0:
            if codec != CIDv0.CODEC:
                raise ValueError(
                    'codec for version 0 can only be {}, found: {}'.format(
                        CIDv0.CODEC, codec))
            return CIDv0(multihash)
        else:
            return CIDv1(codec, multihash)
    else:
        raise ValueError('invalid number of arguments, expected 1 or 3')


def is_cid(cidstr):
    """
    Checks if a given input string is valid encoded CID or not.
    It takes same input as `cid.make_cid` method with a single argument


    :param cidstr: input string which can be a

        - base58-encoded multihash
        - multihash
        - multibase-encoded multihash
    :type cidstr: str or bytes
    :return: if the value is a valid CID or not
    :rtype: bool
    """
    try:
        return bool(make_cid(cidstr))
    except ValueError:
        return False


def from_string(cidstr):
    """
    Creates a CID object from a encoded form

    :param str cidstr: can be

        - base58-encoded multihash
        - multihash
        - multibase-encoded multihash
    :return: a CID object
    :rtype: :py:class:`cid.CIDv0` or :py:class:`cid.CIDv1`
    """
    cidbytes = ensure_bytes(cidstr, 'utf-8')
    return from_bytes(cidbytes)


def from_bytes(cidbytes):
    """
    Creates a CID object from a encoded form

    :param bytes cidbytes: can be

        - base58-encoded multihash
        - multihash
        - multibase-encoded multihash
    :return: a CID object
    :rtype: :py:class:`cid.CIDv0` or :py:class:`cid.CIDv1`
    """
    if multibase.is_encoded(cidbytes):
        # if the bytestream is multibase encoded
        cid = multibase.decode(cidbytes)
        data = cid[1:]
        version = int(cid[0])
        codec = multicodec.get_codec(data)
        multihash = multicodec.remove_prefix(data)

        return make_cid(version, codec, multihash)
    elif cidbytes[0] in (0, 1):
        # if the bytestream is a CID
        version = cidbytes[0]
        data = cidbytes[1:]
        codec = multicodec.get_codec(data)
        multihash = multicodec.remove_prefix(data)

        return make_cid(version, codec, multihash)
    else:
        # otherwise its just base58-encoded multihash
        return make_cid(0, CIDv0.CODEC, base58.b58decode(cidbytes))
