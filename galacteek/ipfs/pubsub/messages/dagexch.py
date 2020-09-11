from galacteek.ipfs.pubsub.messages import PubsubMessage
from galacteek.ipfs.cidhelpers import ipfsCid32Re
from galacteek.core import utcDatetimeIso


class DAGExchangeMessageV1(PubsubMessage):
    TYPE = 'DAGExchangeMessageV1'

    schema = {
        "type": "object",
        "properties": {
            "msgtype": {"type": "string"},
            "version": {"type": "integer"},
            "date": {"type": "string"},
            "exchange": {
                "type": "object",
                "properties": {
                    "megadagcid": {
                        "type": "string",
                        "pattern": ipfsCid32Re.pattern
                    },
                    "dagcid": {
                        "type": "string",
                        "pattern": ipfsCid32Re.pattern
                    },
                    "dagclass": {
                        "type": "string",
                        "pattern": r"\w{2,32}"
                    },
                    "dagnet": {
                        "type": "string",
                        "pattern": r"\w{2,32}"
                    },
                    "dagname": {
                        "type": "string",
                        "pattern": r"\w{2,32}"
                    },
                    "daguid": {
                        "type": "string",
                        "pattern": r"[a-f0-9\-]{36,72}"
                    },
                    "signerpubkeycid": {
                        "type": "string",
                        "pattern": ipfsCid32Re.pattern
                    },
                    "session": {
                        "type": "object",
                        "properties": {
                            "servicetoken": {
                                "type": "string",
                                "pattern": r"[a-f0-9]{64,128}"
                            },
                            "snakeoil": {
                                "type": "string",
                                "pattern": r"[a-f0-9]{128}"
                            }
                        },
                        "required": [
                            "servicetoken",
                            "snakeoil"
                        ]
                    }
                },
                "required": [
                    "megadagcid",
                    "dagcid",
                    "dagclass",
                    "dagnet",
                    "daguid",
                    "signerpubkeycid",
                    "session"
                ]
            }
        },
        "required": ["msgtype", "exchange"]
    }

    @staticmethod
    def make(dagClass: str, dagCid: str,
             dagNet: str, dagName: str,
             dagUid: str,
             signerPubKeyCid: str,
             mDagCid: str,
             serviceToken: str,
             snakeOil: str):
        return DAGExchangeMessageV1({
            'msgtype': DAGExchangeMessageV1.TYPE,
            'version': 1,
            'date': utcDatetimeIso(),
            'exchange': {
                'dagcid': dagCid,
                'megadagcid': mDagCid,
                'dagclass': dagClass,
                'dagnet': dagNet,
                'dagname': dagName,
                'daguid': dagUid,
                'signerpubkeycid': signerPubKeyCid,
                'session': {
                    'servicetoken': serviceToken,
                    'snakeoil': snakeOil
                }
            }
        })

    @property
    def dagClass(self):
        return self.jsonAttr('exchange.dagclass')

    @property
    def dagCid(self):
        return self.jsonAttr('exchange.dagcid')

    @property
    def megaDagCid(self):
        return self.jsonAttr('exchange.megadagcid')

    @property
    def dagUid(self):
        return self.jsonAttr('exchange.daguid')

    @property
    def dagName(self):
        return self.jsonAttr('exchange.dagname')

    @property
    def dagNet(self):
        return self.jsonAttr('exchange.dagnet')

    @property
    def signerPubKeyCid(self):
        return self.jsonAttr('exchange.signerpubkeycid')

    @property
    def serviceToken(self):
        return self.jsonAttr('exchange.session.servicetoken')

    @property
    def snakeOil(self):
        return self.jsonAttr('exchange.session.snakeoil')
