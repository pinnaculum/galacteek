import io
import asyncio

from galacteek import log

from galacteek.core.ps import makeKeyService

from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ipfs import ipfsOp

from galacteek.ld import gLdDefaultContext
from galacteek.services import GService
from galacteek.services import cached_property
from galacteek.services.net.bitmessage.service import BitMessageClientService
from galacteek.services.net.tor.service import TorService
from galacteek.services.net.tor.service import TorServiceRuntimeConfig
from galacteek.services.ethereum.service import EthereumService

from mode.utils.graphs.formatter import *  # noqa
from mode.utils.objects import _label


class AppGraphFormatter(GraphFormatter):
    edge_scheme: Mapping[str, Any] = {
        'color': 'darkseagreen4',
        'arrowcolor': 'red',
        'arrowsize': 0.7,
    }
    node_scheme: Mapping[str, Any] = {
        'fillcolor': 'palegreen3',
        'color': 'palegreen4',
    }
    term_scheme: Mapping[str, Any] = {
        'fillcolor': 'palegreen1',
        'color': 'palegreen2',
    }
    graph_scheme: Mapping[str, Any] = {
        'bgcolor': 'mintcream',
    }

    def dotPath(self, obj) -> str:
        try:
            dotPath = getattr(obj, 'dotPath')
            if dotPath:
                return _label('taillabel', dotPath)
        except Exception:
            return 'Unknown dot path'

    def draw_node(self, obj,
                  scheme: Mapping = None,
                  attrs: Mapping = None) -> str:
        return self.FMT(
            self._node, self.label(obj),
            attrs=self.attrs(attrs, scheme),
        )


class AppService(GService):
    """
    Main service
    """

    name = 'app'

    # Bitmessage service
    bmService: BitMessageClientService = None

    # Tor service
    torService: TorService = None

    # Eth
    ethService: EthereumService = None

    @cached_property
    def bmService(self) -> BitMessageClientService:
        return BitMessageClientService(
            dataPath=self.app._bitMessageDataLocation,
            dotPath='net.bitmessage'
        )

    @cached_property
    def ethService(self) -> EthereumService:
        return EthereumService(
            self.app._ethDataLocation
        )

    @cached_property
    def torService(self) -> TorService:
        return TorService(
            dataPath=self.app.dataPathForService('tor'),
            dotPath='net.tor',
            runtimeConfig=TorServiceRuntimeConfig(
                cfgLocation=self.app._torConfigLocation,
                dataLocation=self.app._torDataDirLocation
            )
        )

    async def on_start(self) -> None:
        await super().on_start()

        log.debug('Starting main application service')

        # Dependencies
        await self.add_runtime_dependency(self.bmService)
        await self.add_runtime_dependency(self.torService)
        await self.add_runtime_dependency(self.ethService)

        # Walk the line
        await self.walkServices('core', add=True)
        await self.walkServices('dweb', add=True)
        await self.walkServices('ld', add=True)

        # Blast
        await self.sServiceStarted.emit()

    async def on_stop(self) -> None:
        await super().on_stop()

        log.debug('Stopping main application service')

    async def rdfStore(self, ipfsPath: IPFSPath,
                       outputGraph: str = 'urn:ipg:i:i0',
                       recordType='OntoloChainRecord',
                       chainUri=None,
                       trace=True):
        await self.ldPublish({
            'type': 'DagRdfStorageRequest',
            'recordType': recordType,
            'historyTrace': trace,
            'chainUri': chainUri,
            'outputGraphIri': outputGraph,
            'ipfsPath': str(ipfsPath)
        }, key=makeKeyService('ld'))

    @ipfsOp
    async def rdfStoreObject(self, ipfsop, obj: dict, iri: str):
        if '@context' not in obj:
            obj['@context'] = gLdDefaultContext

        path = IPFSPath(
            await ipfsop.dagPut(obj)
        )
        if path.valid:
            await self.rdfStore(path, iri)

    @GService.task
    async def mProfileTask(self):
        try:
            from memory_profiler import memory_usage
            assert self.app.cmdArgs.memprofiling is True
        except (ImportError, Exception):
            pass

        while not self.should_stop:
            await asyncio.sleep(10)

            lt = int(self.app.loop.time())

            usage = memory_usage(-1, interval=.2, timeout=1)
            if usage:
                log.debug(
                    f'Memory Usage (LT: {lt}): {usage[0]}'
                )

    async def getGraphImageRaw(self) -> None:
        """
        Return a graph image of the application's service tree,
        in PNG format (raw bytes)

        :rtype: io.BytesIO
        """
        try:
            import pydotplus
        except ImportError:
            return

        try:
            out = io.StringIO()
            beacon = self.beacon.root or self.beacon
            beacon.as_graph().to_dot(out)
            graph = pydotplus.graph_from_dot_data(out.getvalue())
        except Exception as err:
            log.debug(str(err))
            return None
        else:
            return io.BytesIO(graph.create(format='png'))

    async def getGraphImagePil(self) -> None:
        from PIL import Image

        try:
            image = Image.open(await self.getGraphImageRaw())
        except Exception:
            return
        else:
            return image
