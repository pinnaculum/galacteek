
from galacteek import log
from galacteek.ipfs import ipfsOp
from galacteek.ipfs.cidhelpers import IPFSPath

from galacteek.browser.schemes import NativeIPFSSchemeHandler


class IPIDSchemeHandler(NativeIPFSSchemeHandler):
    """
    IPID scheme handler
    """

    @ipfsOp
    async def handleRequest(self, ipfsop, request, uid):
        rUrl = request.requestUrl()
        rMethod = bytes(request.requestMethod()).decode()
        rInitiator = request.initiator().toString()

        # The host is the IPNS key for the DID
        ipnsKey = rUrl.host()
        path = rUrl.path()
        did = f'did:ipid:{ipnsKey}'

        log.debug(f'IPID REQ {rMethod} ({rInitiator}): DID {did}, path {path}')

        ipid = await self.app.ipidManager.load(did)

        if not ipid:
            return self.urlInvalid(request)

        serviceId = did + path

        service = await ipid.searchServiceById(serviceId)
        if not service:
            return self.urlInvalid(request)

        endpoint = service.endpoint

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
