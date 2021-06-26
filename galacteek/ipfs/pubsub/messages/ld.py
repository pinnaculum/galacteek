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
                    "graphIri": {
                        "type": "string",
                        "pattern": r"\w{2,512}"
                    },
                    "sparqlEndpointAddr": {
                        "type": "string",
                        "pattern": r"\w{2,512}"
                    }
                },
                "required": [
                    "graphIri",
                    "sparqlEndpointAddr"
                ]
            }
        }
    },
    "required": ["msgtype", "graphs"]
}


class SparQLHeartbeatMessage(PubsubMessage):
    TYPE = 'SparQLServicesMessage'

    VALID_TYPES = [
        TYPE
    ]

    schema = exchSchema

    @staticmethod
    def make():
        msg = SparQLHeartbeatMessage({
            'msgtype': SparQLHeartbeatMessage.TYPE,
            'version': 1,
            'date': utcDatetimeIso(),
            'graphs': []
        })

        return msg

    @property
    def revision(self):
        return self.jsonAttr('rev')

    @property
    def graphs(self):
        return self.data['graphs']
