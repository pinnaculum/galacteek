"""
Protobuf definitions for IPFS
"""

import base64

from . import unixfs_pb2

from .protobuf_to_dict import protobuf_to_dict


def decodeDagNode(data):
    try:
        message = unixfs_pb2.Data()
        message.MergeFromString(
            base64.b64decode(data))
        obj = protobuf_to_dict(message)
    except Exception:
        return None

    return {
        'type': obj['Type'],
        'size': obj['filesize'],
        'data': obj['Data']
    }
