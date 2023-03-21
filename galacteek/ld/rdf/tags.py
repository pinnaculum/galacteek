import re
from typing import Union

from rdflib import Literal
from rdflib import URIRef
from rdflib import RDF

from galacteek import services
from galacteek import log
from galacteek.core import utcDatetimeIso
from galacteek.ld import ipsTermUri
from galacteek.ld.rdf import BaseGraph
from galacteek.ld.sparql import querydb


TOP_TAGS_GRAPH_URI = 'urn:ipg:i:love:itags'

tagsManagerUri = URIRef('urn:glk:tags:manager')


def getGraph(graphUri: str):
    pronto = services.getByDotName('ld.pronto')
    return pronto.graphByUri(graphUri)


def tagUriFromComponents(comps: list) -> URIRef:
    return URIRef('it:' + ':'.join(comps[0:128]))


def tagUriFromLabel(label: str) -> URIRef:
    """
    Create a it: tag URI from an RDF (@en) label.

    The label is always lowercased (the URI components should be in lowercase).
    """
    try:
        return tagUriFromComponents(
            re.split(r'[^\w\-]{1,256}',
                     label.lower()))
    except Exception:
        log.warning(f'Could not build tag uri from: {label}')
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


def tagWatch(tagUri: URIRef,
             graphUri: str = TOP_TAGS_GRAPH_URI) -> None:
    """
    Start watching/subscribing to a tag
    """

    dstgraph = getGraph(graphUri)

    graph = BaseGraph()
    graph.remove((
        tagsManagerUri,
        ipsTermUri('TagPreferencesManager', fragment='watchTag'),
        tagUri
    ))

    graph.add((
        tagsManagerUri,
        ipsTermUri('TagPreferencesManager', fragment='watchTag'),
        tagUri
    ))

    dstgraph += graph
    dstgraph.publishUpdateEvent(graph)


def tagUnwatch(tagUri: URIRef,
               graphUri: str = TOP_TAGS_GRAPH_URI) -> None:
    """
    Stop watching/subscribing to a tag
    """

    graph = getGraph(graphUri)

    graph.remove((
        tagsManagerUri,
        ipsTermUri('TagPreferencesManager', fragment='watchTag'),
        tagUri
    ))


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
                tagsManagerUri,
                ipsTermUri('TagPreferencesManager', fragment='watchTag'),
                URIRef(tagUri)
            ))

        await graph.guardian.mergeReplace(tagGraph, graph)

        return True

    return False
