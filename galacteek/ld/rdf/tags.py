from rdflib import Literal

from galacteek import services
from galacteek.ld.sparql import querydb


TOP_TAGS_GRAPH_URI = 'urn:ipg:i:love:itags'


def getGraph(graphUri: str):
    pronto = services.getByDotName('ld.pronto')
    return pronto.graphByUri(graphUri)


async def tagsSearch(tagName: str = None,
                     graphUri: str = TOP_TAGS_GRAPH_URI):
    graph = getGraph(graphUri)
    bindings = {}

    if tagName:
        bindings[tagName] = Literal(tagName)

    return await graph.queryAsync(
        querydb.get('TagsSearch'),
        initBindings=bindings
    )
