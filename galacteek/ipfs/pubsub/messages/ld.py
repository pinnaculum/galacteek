from galacteek.ipfs.pubsub.messages import PubsubMessage
from galacteek.ipfs.cidhelpers import ipfsCid32Re
from galacteek.core import utcDatetimeIso


exchSchema = {
    "type": "object",
    "properties": {
        "msgtype": {"type": "string"},
        "version": {"type": "integer"},
        "date": {"type": "string"},
        "rev": {"type": "string"},

        "graphs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "graphExportCid": {
                        "type": "string",
                        "pattern": ipfsCid32Re.pattern
                    },
                    "graphUri": {
                        "type": "string",
                        "pattern": r"\w{2,64}"
                    },
                    "format": {
                        "type": "string",
                        "pattern": r"\w{2,32}"
                    }
                },
                "required": [
                    "graphExportCid",
                    "graphUri"
                ]
            }
        }
    },
    "required": ["msgtype", "graphs"]
}


class RDFGraphsExchangeMessage(PubsubMessage):
    TYPE = 'RDFExchangeMessage'

    VALID_TYPES = [
        TYPE
    ]

    schema = exchSchema

    @staticmethod
    def make(iGraphList):
        msg = RDFGraphsExchangeMessage({
            'msgtype': RDFGraphsExchangeMessage.TYPE,
            'version': 1,
            'date': utcDatetimeIso(),
            'graphs': []
        })
        for name, graph in iGraphList.items():
            if not graph.cid:
                continue

            msg.data['graphs'].append({
                'graphExportCid': graph.cid,
                'graphUri': str(graph.identifier),
                'format': 'ttl'
            })

        return msg

    @property
    def revision(self):
        return self.jsonAttr('rev')

    @property
    def graphs(self):
        return self.data['graphs']


hbSchema = {
    "type": "object",
    "properties": {
        "msgtype": {"type": "string"},
        "version": {"type": "integer"},
        "date": {"type": "string"},
        "rev": {"type": "string"},
        "p2pLibertarianId": {"type": "string"},

        "prontoChainEnv": {
            "type": "string",
            "pattern": r"[a-z]{3,12}"
        },

        "graphs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "graphIri": {
                        "type": "string",
                        "pattern": r"\w{2,512}"
                    },
                    "smartqlEndpointAddr": {
                        "type": "string",
                        "pattern": r"\w{2,512}"
                    },
                    "smartqlCredentials": {
                        "type": "object",
                        "properties": {
                            "user": {
                                "type": "string",
                                "pattern": r"\w{1,64}"
                            },
                            "password": {
                                "type": "string",
                                "pattern": r"\w{1,256}"
                            }
                        }
                    }
                },
                "required": [
                    "graphIri",
                    "smartqlEndpointAddr"
                ]
            }
        }
    },
    "required": ["msgtype", "graphs", "prontoChainEnv"]
}


class SparQLHeartbeatMessage(PubsubMessage):
    TYPE = 'SparQLServicesMessage'

    VALID_TYPES = [
        TYPE
    ]

    schema = hbSchema

    @staticmethod
    def make(prontoEnv: str, libertarianId: str):
        msg = SparQLHeartbeatMessage({
            'msgtype': SparQLHeartbeatMessage.TYPE,
            'version': 1,
            'date': utcDatetimeIso(),
            'prontoChainEnv': prontoEnv,
            'p2pLibertarianId': libertarianId,
            'graphs': []
        })

        return msg

    @property
    def revision(self):
        return self.jsonAttr('rev')

    @property
    def p2pLibertarianId(self):
        return self.jsonAttr('p2pLibertarianId')

    @property
    def prontoChainEnv(self):
        return self.jsonAttr('prontoChainEnv')

    @property
    def graphs(self):
        return self.data['graphs']
