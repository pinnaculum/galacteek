import json
import collections
import base64

from jsonschema import validate
from jsonschema.exceptions import *

from galacteek.core.jtraverse import traverseParser
from galacteek import log

class Encoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, PubsubMessage):
            return obj.data
        if isinstance(obj, MarksBroadcastMessage):
            return obj.data
        if isinstance(obj, PeerIdentMessageV1):
            return obj.data
        return json.JSONEncoder.default(self, obj)

class PubsubMessage(collections.UserDict):
    def __init__(self, *args, **kw):
        super(PubsubMessage, self).__init__(*args, **kw)
        self.schema = None

    def __str__(self):
        return json.dumps(self.data)

    def pretty(self):
        return json.dumps(self.data, indent=4)

    @property
    def parser(self):
        return traverseParser(self.data)

    def validSchema(self, schema=None):
        sch = schema if schema else self.__class__.schema

        try:
            validate(self.data, sch)
        except ValidationError as verr:
            log.debug('Invalid JSON schema error: {}'.format(str(verr)))
            return False
        else:
            return True

    def valid(self):
        return self.validSchema()

    @staticmethod
    def make(*args, **kw):
        raise Exception('Implement static method make')

class MarksBroadcastMessage(PubsubMessage):
    TYPE = 'marksbroadcast'

    @staticmethod
    def make(marksdict):
        msg = MarksBroadcastMessage({
            'msgtype': MarksBroadcastMessage.TYPE,
            'marks': marksdict
        })
        return msg

class PeerIdentMessageV1(PubsubMessage):
    TYPE = 'peerident.v1'

    schema = {
        "title": "Peer ident",
        "description": "Peer identification message, V1",
        "type": "object",
        "properties": {
            "msgtype": {"type": "string"},
            "msg": {
                "type": "object",
                "properties": {
                    "peerid": {"type": "string"},
                    "user": {
                        "type": "object",
                        "properties": {
                            "publicdag": {
                                "type": "object",
                                "properties": {
                                    "cid" : {"type": "string"},
                                    "ipns" : {"type": "string"},
                                    "available" : {"type": "boolean"}
                                }
                            }
                        },
                    },

                    "userinfoobjref": {"type": "string"},
                    "userinfo": {
                        "type": "object",
                        "properties": {
                            "username" : {"type": "string"},
                            "firstname" : {"type": "string"},
                            "lastname" : {"type": "string"},
                            "email" : {"type": "string"},
                            "gender" : {"type": "integer"},
                            "org" : {"type": "string"},
                            "country" : {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "name": {"type": "string"},
                                },
                            },
                            "date" : {"type": "object"},
                            "crypto": {"type": "object"},
                        },
                        "required": [
                            "username",
                            "firstname",
                            "lastname",
                            "email",
                            "gender",
                            "org",
                            "country"
                        ],
                    },
                },
                "required": ["peerid"]
            },
        },
    }

    @staticmethod
    def make(peerId, uInfoCid, userInfo, userDagCid, userDagIpns, p2pServices):
        msg = PeerIdentMessageV1({
            'msgtype': PeerIdentMessageV1.TYPE,
            'version': 1,
            'msg': {
                'peerid': peerId,
                'user': {
                    'publicdag': {
                        'cid': userDagCid,
                        'available': True,
                        'ipns': userDagIpns if userDagIpns else ''
                    },
                },
                'p2pservices': p2pServices,
                'userinfoobjref': uInfoCid,
            }
        })
        msg.data['msg'].update(userInfo)
        return msg

    @property
    def peer(self):
        return self.parser.traverse('msg.peerid')

    @property
    def username(self):
        return self.parser.traverse('msg.userinfo.username')

    @property
    def lastname(self):
        return self.parser.traverse('msg.userinfo.lastname')

    @property
    def country(self):
        return self.parser.traverse('msg.userinfo.country.name')

    @property
    def dateCreated(self):
        return self.parser.traverse('msg.userinfo.date.created')

    @property
    def dagCid(self):
        return self.parser.traverse('msg.user.publicdag.cid')

    @property
    def dagIpns(self):
        return self.parser.traverse('msg.user.publicdag.ipns')

    @property
    def mainPagePath(self):
        return self.parser.traverse('msg.user.mainpage')

    @property
    def userInfoObjCid(self):
        return self.parser.traverse('msg.userinfoobjref')

    @property
    def rsaPubKeyPem(self):
        return self.parser.traverse('msg.userinfo.crypto.rsa.pubkeypem')

    @property
    def msgdata(self):
        return self.data['msg']

    def valid(self):
        return self.validSchema(schema=PeerIdentMessageV1.schema)

class PeerLogoutMessage(PubsubMessage):
    TYPE = 'peerlogout'

    schema = {
        "type" : "object",
        "properties" : {
            "msgtype" : {"type" : "string"},
            "msg" : {
                "type" : "object",
                "properties" : {
                    "peerid" : {"type" : "string"},
                },
                "required": ["peerid"]
            },
        },
    }

    @staticmethod
    def make(peerid):
        msg = PeerLogoutMessage({
            'msgtype': PeerLogoutMessage.TYPE,
            'msg': {
                'peerid': peerid,
            }
        })
        return msg

    @property
    def peer(self):
        return self.parser.traverse('msg.peerid')
