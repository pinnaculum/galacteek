from galacteek.ipfs.pubsub.messages import PubsubMessage
# from galacteek.ipfs.cidhelpers import ipfsCid32Re
from galacteek.core import utcDatetimeIso
from galacteek.did import ipidIdentRe


class IpidServiceExposureMessage(PubsubMessage):
    """
    A message to indicate how an IPID service can expose
    some functionalities through a specific channel like
    a dedicated pubsub topic
    """

    TYPE = 'IpidServiceExposureMessage'

    schema = {
        "type": "object",
        "properties": {
            "msgtype": {"type": "string"},
            "version": {"type": "integer"},
            "date": {"type": "string"},
            "msg": {
                "type": "object",
                "properties": {
                    "did": {
                        "type": "string",
                        "pattern": ipidIdentRe.pattern
                    },
                    "serviceId": {
                        "type": "string"
                    },
                    "pubsubTopic": {
                        "type": "string",
                        "pattern": r"^galacteek\.ipid\.[a-zA-Z-_\.]{1,128}"
                    },
                    "capabilities": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "pattern": r"^[a-zA-Z-_]{1,128}"
                        }
                    }
                },
                "required": ["did", "serviceId"]
            }
        },
        "required": ["msgtype", "msg", "version"]
    }

    @staticmethod
    def make(did: str, serviceId: str, topic: str, caps: list):
        return IpidServiceExposureMessage({
            'msgtype': IpidServiceExposureMessage.TYPE,
            'date': utcDatetimeIso(),
            'version': 1,
            'msg': {
                'did': did,
                'serviceId': serviceId,
                'pubsubTopic': topic,
                'capabilities': caps
            }
        })

    @property
    def did(self):
        return self.jsonAttr('msg.did')

    @property
    def serviceId(self):
        return self.jsonAttr('msg.serviceId')

    @property
    def pubsubTopic(self):
        return self.jsonAttr('msg.pubsubTopic')


class ShortLivedPSChannelMessage(PubsubMessage):
    """
    Message to open short-lived pubsub channels
    """

    TYPE = 'SLPsChannelMessage'

    schema = {
        "type": "object",
        "properties": {
            "msgtype": {"type": "string"},
            "version": {"type": "integer"},
            "date": {"type": "string"},
            "msg": {
                "type": "object",
                "properties": {
                    "pubsubTopic": {
                        "type": "string",
                        "pattern": r"^galacteek\.[0-9a-zA-Z-_\.]{1,512}"
                    },
                    "protocol": {
                        "type": "string"
                    },
                    "capabilities": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "pattern": r"^[a-zA-Z-_]{1,128}"
                        }
                    }
                },
                "required": ["pubsubTopic"]
            }
        },
        "required": ["msgtype", "msg", "version"]
    }

    @staticmethod
    def make(topic: str, protocol: str = 'test/1.0'):
        return ShortLivedPSChannelMessage({
            'msgtype': ShortLivedPSChannelMessage.TYPE,
            'date': utcDatetimeIso(),
            'version': 1,
            'msg': {
                'pubsubTopic': topic,
                'protocol': protocol
            }
        })

    @property
    def did(self):
        return self.jsonAttr('msg.did')

    @property
    def pubsubTopic(self):
        return self.jsonAttr('msg.pubsubTopic')


class DwebPassportMessage(PubsubMessage):
    TYPE = 'IpidPassportMessage'

    schema = {
        "type": "object",
        "properties": {
            "msgtype": {"type": "string"},
            "request": {"type": "string"},
            "version": {"type": "integer"},
            "date": {"type": "string"},
            "msg": {
                "type": "object",
                "properties": {
                    "megaDagCid": {
                        "type": "string"
                    },
                }
            }
        },
        "required": ["request", "msg"]
    }

    @staticmethod
    def make(revision: str):
        return DwebPassportMessage({
            'msgtype': DwebPassportMessage.TYPE,
            'date': utcDatetimeIso(),
            'msg': {
            }
        })
