from aioipfs import APIError


class RemotePinningServiceOps(object):
    async def pinRemoteServiceAdd(self,
                                  serviceName: str,
                                  endpoint: str,
                                  key: str):
        try:
            await self.client.pin.remote.service.add(
                serviceName, endpoint, key)
        except APIError as err:
            self.debug(f'Error adding remote pin service: {err.message}')
            return False
        else:
            return True

    async def pinRemoteServiceRemove(self, serviceName: str):
        try:
            await self.client.pin.remote.service.rm(serviceName)
        except APIError as err:
            self.debug(f'Error removing remote pin service: {err.message}')
            return False
        else:
            return True

    async def pinRemoteServiceList(self, stat=False):
        try:
            return await self.client.pin.remote.service.ls(stat=stat)
        except APIError:
            return None

    async def pinRemoteServiceSearch(self, name):
        try:
            sList = await self.pinRemoteServiceList()
            for service in sList:
                if service['Name'] == name:
                    return service
        except (APIError, Exception):
            return None


class RemotePinningOps(object):
    async def pinRemoteAdd(self,
                           serviceName: str,
                           objPath: str,
                           name=None,
                           background=False):
        try:
            await self.client.pin.remote.add(
                serviceName, objPath, name=name, background=background)
        except APIError as err:
            self.debug(f'Error adding remote pin: {err.message}')
            return False
        else:
            return True

    async def pinRemoteList(self,
                            serviceName: str,
                            name=None,
                            cid: list = [],
                            status: list = ['pinned']):
        try:
            return await self.client.pin.remote.ls(
                serviceName, name=name,
                cid=cid, status=status
            )
        except APIError as err:
            self.debug(f'Error listing remote pins: {err.message}')
            return False

    async def pinRemoteRemove(self,
                              serviceName: str,
                              name=None,
                              cid: list = [],
                              status: list = ['pinned'],
                              force=False):
        try:
            await self.client.pin.remote.rm(
                serviceName, name=name,
                cid=cid, status=status,
                force=force
            )
        except APIError:
            return False
        else:
            return True
