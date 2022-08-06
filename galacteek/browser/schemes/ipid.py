import re

from galacteek import log
from galacteek.ipfs import ipfsOp
from galacteek.ipfs.cidhelpers import IPFSPath

from galacteek.browser.schemes import NativeIPFSSchemeHandler


class IPIDProtocolCommon(object):
    def ipidUrlPathValid(self, path: str) -> bool:
        return re.search(
            r'([\w\/\-\+]+)', path, re.IGNORECASE) is not None


class IPIDRenderer(object):
    async def ipidRenderSummary(self,
                                request,
                                uid,
                                ipid,
                                path='/',
                                rMethod='GET'):
        if rMethod == 'GET':
            services = [s async for s in ipid.discoverServices()]

            return await self.serveTemplate(
                request,
                'ipid/summary.html',
                ipid=ipid,
                services=services
            )


class IPIDSchemeHandler(NativeIPFSSchemeHandler,
                        IPIDRenderer,
                        IPIDProtocolCommon):
    """
    IPID scheme handler
    """

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

        if path == '/':
            return await self.ipidRenderSummary(
                request,
                uid,
                ipid,
                rMethod=rMethod
            )
        elif self.ipidUrlPathValid(path):
            serviceId = ipid.didUrl(path=path)

            service = await ipid.searchServiceById(serviceId)
            if not service:
                return self.urlInvalid(request)

            endpoint = service.endpoint
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
            # rHeaders = request.requestHeaders()
            pass
