import attr


@attr.s(auto_attribs=True)
class GraphSyncConfig:
    # URI of graph synchronizer
    use: str

    hbPeriodicSend: bool = False
    hbIntervalMin: int = 60
    hbIntervalMax: int = 120


@attr.s(auto_attribs=True)
class GraphExportSyncConfig:
    type: str = 'rdfexport'
    format: str = 'ttl'
    compression: str = 'gzip'


@attr.s(auto_attribs=True)
class GraphSparQLSyncConfig:
    type: str = 'sparkie'
    debug: bool = False
    run: list = []


@attr.s(auto_attribs=True)
class GraphSemChainSyncConfig:
    type: str = 'ontolochain'
    recordsPerSync: int = 256
    recordFetchTimeout: int = 30
    syncIntervalMin: int = 60
    chainSyncIntervalMin: int = 90
