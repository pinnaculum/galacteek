from galacteek.ipfs import ipfsOp

from galacteek.browser.schemes import NativeIPFSSchemeHandler


class IPSSchemeHandler(NativeIPFSSchemeHandler):
    """
    IPS scheme handler. Renders IPS JSON-LD schemas in the browser.
    """

    @ipfsOp
    async def handleRequest(self, ipfsop, request, uid):
        rUrl = request.requestUrl()
        ipsKey = rUrl.host()
        rPath = rUrl.path()
        rMethod = bytes(request.requestMethod()).decode()

        rootPath = await self.app.ldSchemas.nsToIpfs(ipsKey)

        if rootPath is None or not rootPath.valid:
            return self.urlInvalid(request)

        if rPath:
            objPath = rootPath.child(rPath)
        else:
            objPath = rootPath

        if rMethod == 'GET':
            return await self.fetchFromPath(ipfsop, request, objPath, uid)
