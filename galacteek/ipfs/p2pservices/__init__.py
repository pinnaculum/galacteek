class P2PService:
    def __init__(self, name, description, protocolName, listenRange,
                 receiver, enabled=True):
        self._name = name
        self._description = description
        self._protocolName = protocolName
        self._listener = None
        self._listenRange = listenRange
        self._enabled = enabled
        self._receiver = receiver

    @property
    def name(self):
        return self._name

    @property
    def enabled(self):
        return self._enabled

    @property
    def description(self):
        return self._description

    @property
    def protocolName(self):
        return self._protocolName

    @property
    def listener(self):
        return self._listener

    @property
    def listenRange(self):
        return self._listenRange

    @property
    def receiver(self):
        return self._receiver

    async def stop(self):
        if self.listener:
            await self.listener.close()
