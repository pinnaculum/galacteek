import re

from rdflib import Literal
from rdflib import URIRef

from PyQt5.QtCore import QUrl

from galacteek import log

from galacteek.ipfs import ipfsOp
from galacteek.ipfs.cidhelpers import IPFSPath

from galacteek.ld import ipsContextUri
from galacteek.ld import ipsTermUri
from galacteek.ld.sparql import querydb

from galacteek.browser.schemes import NativeIPFSSchemeHandler


class IPIDProtocolCommon(object):
    def ipidUrlPathValid(self, path: str) -> bool:
        return re.search(
            r'([\w\/\-\+]+)', path, re.IGNORECASE) is not None


class IPIDTemplatesRenderer(object):
    async def ipidRenderSummary(self,
                                request,
                                uid,
                                ipid,
                                passService,
                                ipidGraph,
                                path='/',
                                rMethod='GET'):
        if rMethod == 'GET':
            services = [s async for s in ipid.discoverServices()]

            return await self.serveTemplate(
                request,
                'ipid/summary.html',
                ipid=ipid,
                services=services,
                passportService=passService,
                ipidg=ipidGraph,
                querydb=querydb,
                Literal=Literal,
                URIRef=URIRef
            )


class IPIDSchemeHandler(NativeIPFSSchemeHandler,
                        IPIDTemplatesRenderer,
                        IPIDProtocolCommon):
    """
    IPID scheme handler
    """

    @ipfsOp
    async def handleService(self, ipfsop, request,
                            reqUid,
                            ipidGraph,
                            serviceId: URIRef,
                            serviceInfo):
        stype = serviceInfo['srvtype']  # noqa
        endpoint = serviceInfo['endpoint']
        eptype = serviceInfo['eptype']

        if not eptype:
            path = IPFSPath(str(endpoint))
            if path.valid:
                return await self.fetchFromPath(ipfsop, request, path, reqUid)

        if eptype == ipsContextUri('HttpForwardServiceEndpoint'):
            url = ipidGraph.value(
                endpoint,
                ipsTermUri('url')
            )

            if url:
                return request.redirect(QUrl(str(url)))

            return self.urlInvalid(request)
        else:
            return self.urlInvalid(request)

    @ipfsOp
    async def handleRequest(self, ipfsop, request, uid):
        endpoint = None
        rUrl = request.requestUrl()
        rMethod = bytes(request.requestMethod()).decode()
        rInitiator = request.initiator().toString()

        # The host is the IPNS key for the DID
        ipnsKey = rUrl.host()
        path = rUrl.path()
        did = f'did:ipid:{ipnsKey}'

        log.debug(f'IPID ({rMethod} request) ({rInitiator}): '
                  f'DID {did}, path {path}')

        ipid = await self.app.ipidManager.load(did)

        if not ipid:
            return self.urlInvalid(request)

        ipidGraph = await ipid.rdfGraph()

        if path in ['/', '/passport']:
            return await self.ipidRenderSummary(
                request,
                uid,
                ipid,
                await ipid.passportService(),
                ipidGraph,
                rMethod=rMethod
            )
        elif self.ipidUrlPathValid(path):
            serviceId = URIRef(ipid.didUrl(path=path))

            try:
                serviceInfo = (list(await ipidGraph.queryAsync(
                    querydb.get('IPIDService'),
                    initBindings={'uri': serviceId}
                ))).pop(0)
            except Exception:
                return self.urlInvalid(request)

            return await self.handleService(request,
                                            uid,
                                            ipidGraph,
                                            serviceId,
                                            serviceInfo)
        else:
            return self.urlInvalid(request)

        if rMethod == 'GET':
            path = IPFSPath(endpoint)
            if path.valid:
                return await self.fetchFromPath(ipfsop, request, path, uid)
            else:
                return self.urlInvalid(request)
        elif rMethod == 'POST':
            # TODO
            pass
