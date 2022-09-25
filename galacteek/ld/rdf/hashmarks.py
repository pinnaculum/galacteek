from datetime import datetime

from rdflib import Literal
from rdflib import URIRef
from rdflib import RDF
from typing import Union
from yarl import URL

from galacteek.core import utcDatetimeIso
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ipfs.mimetype import MIMEType
from galacteek.ipfs.stat import UnixFsStatInfo
from galacteek import services
from galacteek import log
from galacteek.ld import ipsContextUri
from galacteek.ld.sparql import querydb
from galacteek.ld.rdf.terms import HASHMARK


TOP_HASHMARKS_GRAPH_URI = 'urn:ipg:i:love:hashmarks'
MAIN_HASHMARKS_GRAPH_URI = 'urn:ipg:i:love:hashmarks:private'


def getGraph(graphUri: str):
    pronto = services.getByDotName('ld.pronto')
    return pronto.graphByUri(graphUri)


async def getLdHashmark(resourceUri: Union[URIRef, str],
                        graphUri: str = TOP_HASHMARKS_GRAPH_URI):
    graph = getGraph(graphUri)
    subj = resourceUri if isinstance(resourceUri, URIRef) else\
        URIRef(str(resourceUri))

    # TODO: async
    obj = graph.value(
        subject=subj,
        predicate=RDF.type
    )

    if obj != ipsContextUri('Hashmark'):
        # not a hashmark
        return None

    result = list(await graph.queryAsync(
        querydb.get('HashmarksSearch'),
        initBindings={
            'uri': subj,
            'searchQuery': Literal('')
        }
    ))

    if result:
        return result.pop(0)


async def addLdHashmark(resourceUrl: Union[IPFSPath, str, URIRef],
                        title: str,
                        descr: str = None,
                        mimeType: MIMEType = None,
                        objStat: dict = None,
                        filesStat: UnixFsStatInfo = None,
                        size: int = None,
                        score: int = None,
                        comment: str = None,
                        category: str = None,
                        dateCreated: datetime = None,
                        dateFirstSeen: datetime = None,
                        dateLastSeen: datetime = None,
                        graphUri: str = MAIN_HASHMARKS_GRAPH_URI,
                        ipfsObjType: str = 'unixfs',
                        iconUrl: Union[str, URL] = None,
                        imageUriRef: URIRef = None,
                        thumbnailUriRef: URIRef = None,
                        metaLangTag: str = 'en',
                        schemePreferred: str = None,
                        referencedBy: list = [],
                        keywordMatch: list = [''],
                        libertarianId: URIRef = None,
                        **extra):
    debug = extra.get('debug', False)
    refs = []
    iPath, uRef = None, None
    pronto = services.getByDotName('ld.pronto')
    graph = getGraph(graphUri)

    if graph is None:
        return False

    libertarianId = libertarianId if libertarianId else \
        await pronto.getLibertarianId()

    if isinstance(resourceUrl, IPFSPath):
        iPath = resourceUrl
    elif isinstance(resourceUrl, str):
        uRef = URIRef(resourceUrl)
    elif isinstance(resourceUrl, URIRef):
        uRef = resourceUrl

    # TODO
    # Handle different @language codes (fixed to en for now)

    hmark = {
        '@type': 'Hashmark',

        'title': {
            metaLangTag: title
        },
        'description': {
            metaLangTag: descr
        },
        'keywordMatch': keywordMatch,

        'dateCreated': dateCreated.isoformat() if dateCreated else
        utcDatetimeIso()
    }

    if iPath and iPath.valid:
        hmark['@id'] = str(iPath.ipfsUriRef)
        hmark['ipfsPath'] = iPath.objPath
        # hmark['ipfsObjType'] = ipfsObjType

        if isinstance(objStat, dict):
            # Object stat result
            # hmark['size'] = objStat['CumulativeSize']
            hmark['ipfsObjectStat'] = {
                '@type': 'IpfsObjectStatResult',
                '@id': hmark['@id'] + '#ipfsObjectStat'
            }
            hmark['ipfsObjectStat'].update(objStat)

        if isinstance(filesStat, UnixFsStatInfo) and filesStat.stat:
            # Files stat result
            hmark['ipfsUnixFsStat'] = {
                '@type': 'UnixFsStatResult',
                '@id': hmark['@id'] + '#ipfsUnixFsStat'
            }
            hmark['ipfsUnixFsStat'].update(filesStat.stat)

    elif uRef:
        # Non-IPFS urls
        hmark['@id'] = str(uRef)
    else:
        # Non-IPFS urls
        hmark['@id'] = str(resourceUrl)

    if isinstance(mimeType, MIMEType):
        hmark['mimeType'] = str(mimeType)
        hmark['mimeCategory'] = mimeType.category

    if schemePreferred:
        hmark['schemePreferred'] = schemePreferred

    if category:
        hmark['category'] = {
            metaLangTag: category
        }

    if comment:
        hmark['comment'] = {
            metaLangTag: comment
        }

    if iconUrl:
        hmark['icon'] = {
            '@type': 'ImageObject',
            '@id': str(iconUrl),
            'contentUrl': str(iconUrl)
            # 'url': str(iconUrl)
        }

    if imageUriRef:
        hmark['image'] = {
            '@id': str(imageUriRef),
            '@type': 'ImageObject',
            'contentUrl': str(imageUriRef)
        }

    if thumbnailUriRef:
        hmark['thumbnail'] = {
            '@id': str(thumbnailUriRef),
            '@type': 'ImageObject',
            'contentUrl': str(thumbnailUriRef)
        }

    if isinstance(size, int):
        hmark['size'] = size

    if type(score) in [int, float]:
        hmark['score'] = score

    if libertarianId:
        hmark['fromLibertarian'] = str(libertarianId)

    refs = []
    for ref in referencedBy:
        p = IPFSPath(ref)
        if p.valid:
            refs.append(p.ipfsUrl)

    if refs:
        hmark['referencedBy'] = refs

    for name, v in extra.items():
        hmark[name] = v

    hmg = await graph.rdfifyObject(hmark)

    if hmg:
        if debug:
            print((await hmg.ttlize()).decode())

        return await graph.guardian.mergeReplace(hmg, graph)
    else:
        log.warning(f'Could not graph: {resourceUrl}')
        return False


async def ldHashmarksByTag(tagUri: URIRef = None,
                           graphUri: str = TOP_HASHMARKS_GRAPH_URI):
    graph = getGraph(graphUri)

    return await graph.queryAsync(
        querydb.get('HashmarkTagsSearch'),
        initBindings={'taguri': tagUri}
    )


def ldHashmarkTag(hashmarkUri: URIRef,
                  tag: URIRef,
                  graphUri: str = MAIN_HASHMARKS_GRAPH_URI):
    graph = getGraph(graphUri)
    graph.add((
        hashmarkUri,
        HASHMARK.tag,
        tag
    ))

    graph.publishUpdateEvent()


def ldHashmarkUntag(hashmarkUri: URIRef,
                    tag: URIRef,
                    graphUri: str = MAIN_HASHMARKS_GRAPH_URI):
    graph = getGraph(graphUri)
    graph.remove((
        hashmarkUri,
        HASHMARK.tag,
        tag
    ))

    graph.publishUpdateEvent()


def hashmarkTagsUpdate(hashmarkUri: URIRef,
                       tags: list = [],
                       graphUri: str = MAIN_HASHMARKS_GRAPH_URI):
    graph = getGraph(graphUri)
    graph.remove((
        hashmarkUri,
        HASHMARK.tag,
        None
    ))

    for tag in tags:
        ldHashmarkTag(hashmarkUri, tag, graphUri=graphUri)

    graph.publishUpdateEvent()


async def tagsForHashmark(hmUri: URIRef,
                          graphUri: str = TOP_HASHMARKS_GRAPH_URI):
    graph = getGraph(graphUri)

    return await graph.queryAsync(
        querydb.get('HashmarkTags'),
        initBindings={'hmuri': hmUri}
    )


async def searchLdHashmarks(title: str = '',
                            langTag: str = 'en',
                            extraBindings: dict = {},
                            rq: str = 'HashmarksSearch',
                            graphUri: str = 'urn:ipg:i:love:hashmarks'):
    """
    Search for hashmarks in the RDF graph

    :param str title: title to look for
    :param str langTag: language tag filter
    :param str graphUri: Pronto RDF graph URI
    :param dict extraBindings: a dictionary of extra SparQL bindings
        to pass in the query
    """
    pronto = services.getByDotName('ld.pronto')
    graph = pronto.graphByUri(graphUri)
    query = querydb.get(rq)

    if graph is None or not query:
        return None

    bindings = {}
    bindings['searchQuery'] = Literal(title)
    bindings['langTagMatch'] = Literal(langTag)

    if extraBindings:
        bindings.update(extraBindings)

    return await graph.queryAsync(query, initBindings=bindings)
