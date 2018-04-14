import json
import collections

class Encoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, PubsubMessage):
            return obj.data
        if isinstance(obj, MarksBroadcastMessage):
            return obj.data
        return json.JSONEncoder.default(self, obj)

class PubsubMessage(collections.UserDict):
    def __str__(self):
        return json.dumps(self.data, indent=4, cls=Encoder)

class MarksBroadcastMessage(PubsubMessage):
    TYPE = 'marksbroadcast'

    @staticmethod
    def make(marksdict):
        msg = MarksBroadcastMessage({
            'msgtype': MarksBroadcastMessage.TYPE,
            'marks': marksdict
        })
        return msg
