
class P2PService:
    def __init__(self, name, description, protocolName):
        self._name = name
        self._description = description
        self._protocolName = protocolName
        self._listener = None

    @property
    def name(self):
        return self._name

    @property
    def description(self):
        return self._description

    @property
    def protocolName(self):
        return self._protocolName

    @property
    def listener(self):
        return self._listener

    async def createListener(self, *args, **kw):
        pass

    async def stop(self):
        if self.listener:
            await self.listener.close()
