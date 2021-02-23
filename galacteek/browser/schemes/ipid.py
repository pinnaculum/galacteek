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

        # The host is the IPNS key for the DID
        ipnsKey = rUrl.host()
        path = rUrl.path()
        did = f'did:ipid:{ipnsKey}'

        ipid = await self.app.ipidManager.load(did)
        print(ipid)

        if not ipid:
            return self.urlInvalid(request)

        serviceId = did + path
        print(serviceId)

        service = await ipid.searchServiceById(serviceId)
        if not service:
            return self.urlInvalid(request)

        endpoint = service.endpoint
        print(endpoint)

        path = IPFSPath(endpoint)
        if path.valid:
            return await self.fetchFromPath(ipfsop, request, path, uid)
        else:
            return self.urlInvalid(request)
