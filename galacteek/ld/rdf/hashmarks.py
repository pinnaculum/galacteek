from datetime import datetime

from rdflib import Literal
from rdflib import URIRef
from rdflib import RDF
from typing import Union
from yarl import URL

from galacteek.core import utcDatetimeIso
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ipfs.mimetype import MIMEType
from galacteek import services
from galacteek.ld import ipsContextUri
from galacteek.ld.sparql import querydb
from galacteek.ld.rdf.terms import HASHMARK


TOP_HASHMARKS_GRAPH_URI = 'urn:ipg:i:love:hashmarks'
MAIN_HASHMARKS_GRAPH_URI = 'urn:ipg:i:love:hashmarks:main'


def getGraph(graphUri: str):
    pronto = services.getByDotName('ld.pronto')
    return pronto.graphByUri(graphUri)


async def getLdHashmark(resourceUri: URIRef,
                        graphUri: str = TOP_HASHMARKS_GRAPH_URI):
    graph = getGraph(graphUri)

    # TODO: async
    obj = graph.value(
        subject=resourceUri,
        predicate=RDF.type
    )

    if obj != ipsContextUri('Hashmark'):
        # not a hashmark
        return None

    result = list(await graph.queryAsync(
        querydb.get('HashmarksSearch'),
        initBindings={
            'uri': resourceUri,
            'titleSearch': Literal('')
        }
    ))

    if result:
        return result.pop(0)


async def addLdHashmark(resourceUrl: Union[IPFSPath, str, URIRef],
                        title: str,
                        descr: str,
                        mimeType: MIMEType = None,
                        objStat: dict = None,
                        size: int = 0,
                        score: int = 0,
                        comment: str = None,
                        category: str = None,
                        dateCreated: datetime = None,
                        graphUri: str = MAIN_HASHMARKS_GRAPH_URI,
                        ipfsObjType: str = 'unixfs',
                        iconUrl: Union[str, URL] = None,
                        imageUriRef: URIRef = None,
                        metaLangTag: str = 'en',
                        schemePreferred: str = None,
                        referencedBy: list = [],
                        keywordMatch: list = [],
                        libertarianId: URIRef = None,
                        **extra):
    refs = []
    iPath, uRef = None, None
    pronto = services.getByDotName('ld.pronto')
    graph = getGraph(graphUri)

    if graph is None:
        return False

    libertarianId = libertarianId if libertarianId else \
        await pronto.getLibertarianId()

    mType = MIMEType(mimeType) if isinstance(mimeType, str) else None

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


        # 'keywordMatch': [''],
        'dateCreated': dateCreated if dateCreated else utcDatetimeIso()
    }

    if iPath and iPath.valid:
        hmark['@id'] = str(iPath.ipfsUriRef)
        hmark['ipfsPath'] = iPath.objPath
        hmark['ipfsObjType'] = ipfsObjType

        if isinstance(objStat, dict):
            # hmark['size'] = objStat['CumulativeSize']
            hmark['ipfsObjectStat'] = {
                '@type': 'IpfsObjectStatResult',
                '@id': hmark['@id'] + '#ipfsObjectStat'
            }
            hmark['ipfsObjectStat'].update(objStat)

    elif uRef:
        # Non-IPFS urls
        hmark['@id'] = str(uRef)
    else:
        # Non-IPFS urls
        hmark['@id'] = str(resourceUrl)

    if mType:
        hmark['mimeType'] = str(mType)
        hmark['mimeCategory'] = mType.category

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

    if mType:
        hmark['mimeType'] = str(mType)

    if iconUrl:
        hmark['icon'] = {
            '@id': iconUrl,
            '@type': 'ImageObject',
            'url': iconUrl
        }

    if imageUriRef:
        hmark['image'] = {
            '@id': str(imageUriRef),
            '@type': 'ImageObject',
            'url': str(imageUriRef)
        }

    if libertarianId:
        hmark['fromLibertarian'] = str(libertarianId)

    refs = []
    for ref in referencedBy:
        p = IPFSPath(ref)
        if p.valid:
            refs.append(p.ipfsUrl)

    for name, v in extra.items():
        hmark[name] = v

    # await graph.pullObject(hmark)

    hmg = await graph.rdfifyObject(hmark)

    await graph.guardian.mergeReplace(
        hmg, graph
    )

    return True


async def tagsSearch(tagName: str = None,
                     graphUri: str = TOP_HASHMARKS_GRAPH_URI):
    graph = getGraph(graphUri)

    return await graph.queryAsync(
        querydb.get('HashmarkTagsSearch')
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


def ldHashmarkUntag(hashmarkUri: URIRef,
                    tag: URIRef,
                    graphUri: str = MAIN_HASHMARKS_GRAPH_URI):
    graph = getGraph(graphUri)
    graph.remove((
        hashmarkUri,
        HASHMARK.tag,
        tag
    ))


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


async def searchLdHashmarks(title: str = None,
                            langTag: str = 'en',
                            graphUri: str = 'urn:ipg:i:love:hashmarks'):
    """
    Search for hashmarks in the RDF graph

    :param str title: title to look for
    :param str langTag: language tag filter
    :param str graphUri: Pronto RDF graph URI
    """
    pronto = services.getByDotName('ld.pronto')
    graph = pronto.graphByUri(graphUri)
    query = querydb.get('HashmarksSearch')

    if graph is None or not query:
        return None

    bindings = {}
    if title:
        bindings['titleSearch'] = Literal(title)

    bindings['langtag'] = Literal(langTag)

    return await graph.queryAsync(query, initBindings=bindings)
