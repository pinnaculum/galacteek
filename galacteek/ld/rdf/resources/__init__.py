from rdflib.resource import Resource


class IPR(Resource):
    def replace(self, p, o):
        self.remove(p)
        self.add(p, o)
