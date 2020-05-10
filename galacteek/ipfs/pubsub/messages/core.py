from galacteek.core import utcDatetimeIso
from galacteek.core.iphandle import ipHandleRe
from galacteek.ipfs.cidhelpers import ipfsCid32Re
from galacteek.ipfs.cidhelpers import stripIpfs
from galacteek.ipfs.pubsub.messages import PubsubMessage
from galacteek.did import ipidIdentRe


class MarksBroadcastMessage(PubsubMessage):
    TYPE = 'hashmarks.broadcast'

    schema = {
        "title": "Hashmarks broadcast",
        "description": "Hashmarks broadcast message",
        "type": "object",
        "properties": {
            "msgtype": {"type": "string"},
            "msg": {
                "type": "object",
                "properties": {
                    "peerid": {"type": "string"},
                    "ipfsmarks": {
                        "type": "object",
                        "properties": {
                            "categories": {"type": "object"}
                        }
                    }
                },
                "required": ["peerid", "ipfsmarks"]
            },
        },
        "required": ["msgtype", "msg"]
    }

    @staticmethod
    def make(peerid, ipfsmarks):
        msg = MarksBroadcastMessage({
            'msgtype': MarksBroadcastMessage.TYPE,
            'date': utcDatetimeIso(),
            'msg': {
                'peerid': peerid,
                'ipfsmarks': ipfsmarks
            }
        })
        return msg

    @property
    def peer(self):
        return self.jsonAttr('msg.peerid')

    @property
    def marks(self):
        return self.jsonAttr('msg.ipfsmarks')


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
                                    "cid": {"type": "string"},
                                    "ipns": {"type": "string"},
                                    "available": {"type": "boolean"}
                                },
                                "required": [
                                    "ipns",
                                    "cid"
                                ],
                            }
                        },
                        "required": [
                            "publicdag"
                        ],
                    },
                    "userinfo": {
                        "type": "object",
                        "properties": {
                            "username": {"type": "string"},
                            "firstname": {"type": "string"},
                            "lastname": {"type": "string"},
                            "altname": {"type": "string"},
                            "email": {"type": "string"},
                            "gender": {"type": "integer"},
                            "org": {"type": "string"},
                            "city": {"type": "string"},
                            "country": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "name": {"type": "string"},
                                },
                            },
                            "date": {"type": "object"},
                            "crypto": {
                                "type": "object",
                                "properties": {
                                    "rsa": {
                                        "type": "object",
                                        "properties": {
                                            "pubkeypem": {"type": "string"}
                                        }
                                    }
                                },
                                "required": [
                                    "rsa"
                                ]
                            }
                        },
                        "required": [
                            "username",
                            "firstname",
                            "lastname",
                            "email",
                            "gender",
                            "org",
                            "city",
                            "identtoken",
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
                'p2pservices': p2pServices
            }
        })
        msg.data['msg'].update(userInfo)
        return msg

    @property
    def peer(self):
        return self.jsonAttr('msg.peerid')

    @property
    def username(self):
        return self.jsonAttr('msg.userinfo.username')

    @property
    def lastname(self):
        return self.jsonAttr('msg.userinfo.lastname')

    @property
    def country(self):
        return self.jsonAttr('msg.userinfo.country.name')

    @property
    def city(self):
        return self.jsonAttr('msg.userinfo.city')

    @property
    def location(self):
        if self.country != '' and self.city != '':
            return '{city}, {country}'.format(
                city=self.city,
                country=self.country
            )
        elif self.country != '':
            return self.country
        else:
            return 'Unknown'

    @property
    def dateCreated(self):
        return self.jsonAttr('msg.userinfo.date.created')

    @property
    def dagCid(self):
        return self.jsonAttr('msg.user.publicdag.cid')

    @property
    def dagIpns(self):
        return self.jsonAttr('msg.user.publicdag.ipns')

    @property
    def mainPagePath(self):
        return self.jsonAttr('msg.user.mainpage')

    @property
    def userInfoObjCid(self):
        return self.jsonAttr('msg.userinfoobjref')

    @property
    def rsaPubKeyPem(self):
        return self.jsonAttr('msg.userinfo.crypto.rsa.pubkeypem')

    @property
    def msgdata(self):
        return self.data['msg']

    def valid(self):
        return self.validSchema(schema=PeerIdentMessageV1.schema)


class PeerIdentMessageV2(PubsubMessage):
    TYPE = 'peerident.v2'

    schema = {
        "title": "Peer ident",
        "description": "Peer identification message, V2",
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
                                    "cid": {"type": "string"},
                                    "ipns": {"type": "string"},
                                    "available": {"type": "boolean"}
                                },
                                "required": [
                                    "ipns",
                                    "cid"
                                ],
                            }
                        },
                        "required": [
                            "publicdag"
                        ],
                    },
                    "userinfo": {
                        "type": "object",
                        "properties": {
                            "username": {"type": "string"},
                            "firstname": {"type": "string"},
                            "lastname": {"type": "string"},
                            "altname": {"type": "string"},
                            "email": {"type": "string"},
                            "gender": {"type": "integer"},
                            "org": {"type": "string"},
                            "city": {"type": "string"},
                            "country": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "name": {"type": "string"},
                                },
                            },
                            "date": {"type": "object"},
                            "crypto": {
                                "type": "object",
                                "properties": {
                                    "rsa": {
                                        "type": "object",
                                        "properties": {
                                            "pubkeypem": {"type": "string"}
                                        }
                                    }
                                },
                                "required": [
                                    "rsa"
                                ]
                            }
                        },
                        "required": [
                            "username",
                            "firstname",
                            "lastname",
                            "email",
                            "gender",
                            "org",
                            "city",
                            "identtoken",
                            "country"
                        ],
                    },
                },
                "required": ["peerid"]
            },
        },
        "required": ["msgtype", "msg"]
    }

    @staticmethod
    def make(peerId, uInfoCid, userInfo, userDagCid, userDagIpns, p2pServices,
             orbitCfgMaps):
        msg = PeerIdentMessageV2({
            'msgtype': PeerIdentMessageV2.TYPE,
            'date': utcDatetimeIso(),
            'version': 2,
            'msg': {
                'peerid': peerId,
                'user': {
                    'publicdag': {
                        'cid': userDagCid,
                        'available': True,
                        'ipns': userDagIpns if userDagIpns else ''
                    },
                },
                'orbitcfgmaps': orbitCfgMaps,
                'p2pservices': p2pServices
            }
        })
        msg.data['msg'].update(userInfo)
        return msg

    @property
    def peer(self):
        return self.jsonAttr('msg.peerid')

    @property
    def username(self):
        return self.jsonAttr('msg.userinfo.username')

    @property
    def lastname(self):
        return self.jsonAttr('msg.userinfo.lastname')

    @property
    def country(self):
        return self.jsonAttr('msg.userinfo.country.name')

    @property
    def city(self):
        return self.jsonAttr('msg.userinfo.city')

    @property
    def location(self):
        if self.country != '' and self.city != '':
            return '{city}, {country}'.format(
                city=self.city,
                country=self.country
            )
        elif self.country != '':
            return self.country
        else:
            return 'Unknown'

    @property
    def dateCreated(self):
        return self.jsonAttr('msg.userinfo.date.created')

    @property
    def dagCid(self):
        return self.jsonAttr('msg.user.publicdag.cid')

    @property
    def dagIpns(self):
        return self.jsonAttr('msg.user.publicdag.ipns')

    @property
    def mainPagePath(self):
        return self.jsonAttr('msg.user.mainpage')

    @property
    def userInfoObjCid(self):
        return self.jsonAttr('msg.userinfoobjref')

    @property
    def rsaPubKeyPem(self):
        return self.jsonAttr('msg.userinfo.crypto.rsa.pubkeypem')

    @property
    def msgdata(self):
        return self.data['msg']

    def valid(self):
        return self.validSchema(schema=PeerIdentMessageV2.schema)


class PeerIdentMessageV3(PubsubMessage):
    TYPE = 'peerident.v3'

    schema = {
        "title": "Peer ident",
        "description": "Peer identification message, V3",
        "type": "object",
        "properties": {
            "msgtype": {
                "type": "string",
                "pattern": "^{0}$".format(TYPE)
            },
            "msg": {
                "type": "object",
                "properties": {
                    "peerid": {"type": "string"},
                    "user": {
                        "type": "object",
                        "properties": {
                            "identity": {
                                "type": "object",
                                "properties": {
                                    "vplanet": {
                                        "type": "string"
                                    },
                                    "iphandle": {
                                        "type": "string",
                                        "pattern": ipHandleRe.pattern
                                    },
                                    "persondid": {
                                        "type": "string",
                                        "pattern": ipidIdentRe.pattern
                                    },
                                    "iphandleqrpngcid": {
                                        "type": "string",
                                        "pattern": ipfsCid32Re.pattern
                                    },
                                    "orgs": {
                                        "type": "array",
                                        "items": {
                                            "type": "string",
                                            "pattern": ipidIdentRe.pattern
                                        }
                                    }
                                },
                                "required": [
                                    "vplanet",
                                    "iphandle",
                                    "iphandleqrpngcid",
                                    "persondid"
                                ]
                            }
                        },
                        "required": [
                            "identity"
                        ],
                    }
                },
                "required": ["peerid"]
            },
        },
        "required": ["msgtype", "msg"]
    }

    @staticmethod
    async def make(peerId, userDagCid, userDagIpns, userInfo,
                   personDid, personDidCurCid,
                   p2pServices=None):
        p2pServices = p2pServices if p2pServices else []
        qrPngNodeCid = stripIpfs(
            await userInfo.identityResolve('iphandleqr/png')
        )

        msg = PeerIdentMessageV3({
            'msgtype': PeerIdentMessageV3.TYPE,
            'date': utcDatetimeIso(),
            'msg': {
                'peerid': peerId,
                'user': {
                    'identity': {
                        'vplanet': userInfo.vplanet,
                        'iphandle': userInfo.iphandle,
                        'iphandleqrpngcid': qrPngNodeCid,
                        'persondid': userInfo.personDid,
                        'persondidcurrentcid': personDidCurCid,
                        'orgs': []
                    },
                    'p2pservices': p2pServices
                }
            }
        })
        return msg

    @property
    def peer(self):
        return self.jsonAttr('msg.peerid')

    @property
    def iphandle(self):
        return self.jsonAttr('msg.user.identity.iphandle')

    @property
    def iphandleqrpngcid(self):
        return self.jsonAttr('msg.user.identity.iphandleqrpngcid')

    @property
    def vplanet(self):
        return self.jsonAttr('msg.user.identity.vplanet')

    @property
    def personDid(self):
        return self.jsonAttr('msg.user.identity.persondid')

    @property
    def personDidCurCid(self):
        return self.jsonAttr('msg.user.identity.persondidcurrentcid')

    def dateMessage(self):
        return self.jsonAttr('date')

    @property
    def msgdata(self):
        return self.data['msg']

    def valid(self):
        return self.validSchema(schema=PeerIdentMessageV3.schema)


class PeerIpHandleChosen(PubsubMessage):
    TYPE = 'peeriphandlechange'

    schema = {
        "title": "Peer IP name",
        "description": "Peer IP name",
        "type": "object",
        "properties": {
            "msgtype": {
                "type": "string",
                "pattern": "^{0}$".format(TYPE)
            },
            "msg": {
                "type": "object",
                "properties": {
                    "peerid": {"type": "string"},
                    "iphandle": {
                        "type": "string",
                        "pattern": ipHandleRe.pattern
                    },
                    "iphandleqrpngcid": {"type": "string"}
                },
                "required": [
                    "iphandle",
                    "iphandleqrpngcid"
                ]
            }
        },
        "required": ["msgtype", "msg"]
    }

    @staticmethod
    def make(peerId, ipHandle: str,
             ipHandleQrCid: str,
             ipHandleQrPngCid: str):

        msg = PeerIpHandleChosen({
            'msgtype': PeerIpHandleChosen.TYPE,
            'date': utcDatetimeIso(),
            'msg': {
                'peerid': peerId,
                'iphandle': ipHandle,
                'iphandleqrrawcid': ipHandleQrCid,
                'iphandleqrpngcid': ipHandleQrPngCid
            }
        })
        return msg

    @property
    def peer(self):
        return self.jsonAttr('msg.peerid')

    @property
    def iphandle(self):
        return self.jsonAttr('msg.iphandle')


class PeerLogoutMessage(PubsubMessage):
    TYPE = 'peerlogout'

    schema = {
        "type": "object",
        "properties": {
            "msgtype": {"type": "string"},
            "msg": {
                "type": "object",
                "properties": {
                    "peerid": {"type": "string"},
                },
                "required": ["peerid"]
            },
        },
        "required": ["msgtype", "msg"]
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
        return self.jsonAttr('msg.peerid')

    def valid(self):
        return self.validSchema(schema=PeerLogoutMessage.schema)
