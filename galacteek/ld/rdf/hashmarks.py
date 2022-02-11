from galacteek.core import utcDatetimeIso
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ipfs.mimetype import MIMEType
from galacteek import services


async def addLdHashmark(graphUri,
                        iPath: IPFSPath,
                        title: str,
                        descr: str,
                        mimeType: str,
                        size: int,
                        **extra):

    pronto = services.getByDotName('ld.pronto')
    graph = pronto.graphByUri(graphUri)

    if graph is None:
        return False

    mType = MIMEType(mimeType)

    hmark = {
        '@type': 'Hashmark',
        '@id': iPath.ipfsUrl,

        'ipfsPath': iPath.objPath,
        'ipfsObjType': 'unixfs',
        'title': title,
        'description': descr,
        'size': size,
        'mimeType': str(mType),
        'mimeCategory': mType.category,
        'keywordMatch': [''],
        'dateCreated': utcDatetimeIso()
    }

    for name, v in extra.items():
        hmark[name] = v

    await graph.pullObject(hmark)

    return True
