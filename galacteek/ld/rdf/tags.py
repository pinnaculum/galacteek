import re
from typing import Union

from rdflib import Literal
from rdflib import URIRef
from rdflib import RDF

from galacteek import services
from galacteek.core import utcDatetimeIso
from galacteek.ld import ipsTermUri
from galacteek.ld.sparql import querydb


TOP_TAGS_GRAPH_URI = 'urn:ipg:i:love:itags'


def getGraph(graphUri: str):
    pronto = services.getByDotName('ld.pronto')
    return pronto.graphByUri(graphUri)


def tagUriFromComponents(comps: list) -> URIRef:
    return URIRef('it:' + ':'.join(comps[0:128]))


def tagUriFromLabel(label: str) -> URIRef:
    """
    Create a it: tag URI from an RDF (@en) label
    """
    try:
        return tagUriFromComponents(
            re.split(r'[^\w\-]{1,256}',
                     label))
    except Exception:
        return None


async def tagsSearch(tagName: str = None,
                     graphUri: str = TOP_TAGS_GRAPH_URI):
    graph = getGraph(graphUri)
    bindings = {}

    if tagName:
        bindings['tagName'] = Literal(tagName)

    return await graph.queryAsync(
        querydb.get('TagsSearch'),
        initBindings=bindings
    )


async def tagCreate(tagUri: Union[str, URIRef],
                    tagNames: dict = {},
                    tagDisplayNames: dict = {},
                    shortDescription: dict = {},
                    meanings: list = [],
                    watch: bool = False,
                    priority: int = None,
                    graphUri: str = TOP_TAGS_GRAPH_URI) -> bool:
    """
    Create a new tag

    :param str tagUri: URI of the tag (it:tagname..)
    :param dict tagNames: Tag names by language
    :param dict tagDisplayNames: Tag display names by language
    :param list meaning: Tag meanings list
    :param bool watch: Watch this tag (tag preferences manager)
    :rtype: bool
    """

    graph = getGraph(graphUri)

    stype = graph.value(
        subject=tagUri,
        predicate=RDF.type
    )

    if stype:
        return False

    tag = {
        '@type': 'Tag',
        '@id': str(tagUri),

        'name': tagNames,
        'displayName': tagDisplayNames,
        'shortDescription': shortDescription,

        'means': meanings,

        'dateCreated': utcDatetimeIso()
    }

    if isinstance(priority, int) and priority > 0:
        tag['priority'] = priority

    tagGraph = await graph.rdfifyObject(tag)

    if tagGraph:
        if watch is True:
            graph.add((
                URIRef('urn:glk:tags:manager'),
                ipsTermUri('TagPreferencesManager', fragment='watchTag'),
                URIRef(tagUri)
            ))

        await graph.guardian.mergeReplace(tagGraph, graph)

        return True

    return False
