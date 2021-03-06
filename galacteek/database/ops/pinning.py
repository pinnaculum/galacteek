from galacteek.database.models.ipfs import *  # noqa


async def remotePinningServicesList():
    """
    Unused
    """
    return await IPFSRemotePinningService.all()


async def remotePinningServiceAdd(name: str,
                                  endpoint: str,
                                  secret: str):
    """
    Unused, would primarily be used to make backups of
    RPS API keys
    """
    try:
        service = IPFSRemotePinningService(
            name=name,
            endpoint=endpoint,
            key=secret,
            enabled=True
        )
        await service.save()
    except Exception:
        pass
    else:
        return service
