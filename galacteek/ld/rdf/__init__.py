import asyncio
import io
from pathlib import Path

from rdflib import Graph
from rdflib import Literal
from rdflib import BNode
from rdflib import Namespace
from rdflib.namespace import NamespaceManager

from galacteek import log
from galacteek import AsyncSignal
from galacteek.core.asynclib import asyncWriteFile


# Default NS bindings used by BaseGraph
nsBindings = {
    'dc': 'http://purl.org/dc/terms/',
    'gs': [
        'ips://galacteek.ld/',
        'ipschema://galacteek.ld.contexts/',
    ],
    'schema': 'https://schema.org/',
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
    'sec': 'https://w3id.org/security#',
    'didv': 'https://w3id.org/did#'
}


def purgeBlank(graph: Graph):
    cn = 0

    for s, p, o in graph:
        if isinstance(s, BNode) or isinstance(o, BNode):
            graph.remove((s, p, o))
            cn += 1

            log.debug(f'BNode purge object: {s}:{o} ({p})')

    return cn


class BaseGraph(Graph):
    def __init__(self, *args, **kw):
        super(BaseGraph, self).__init__(*args, **kw)

        self.iNsBind()

    def iNsBind(self):
        self.iNs = NamespaceManager(self)

        # Bind some useful things in the NS manager
        for ns, uri in nsBindings.items():
            if isinstance(uri, list):
                [self.iNs.bind(ns, Namespace(u)) for u in uri]
            else:
                self.iNs.bind(ns, Namespace(uri))

    @property
    def nameSpaces(self):
        return [n for n in self.iNs.namespaces()]


class IGraph(BaseGraph):
    def __init__(self, name, rPath: Path, store, **kw):
        super(IGraph, self).__init__(store, **kw)

        self.loop = asyncio.get_event_loop()

        self.name = name
        self.rPath = rPath
        self.exportsPath = self.rPath.joinpath('exports')
        self.exportsPath.mkdir(parents=True, exist_ok=True)
        self.xmlExportPath = self.exportsPath.joinpath('graph.xml')

        self.trailPath = self.rPath.joinpath('trail.json')

        # self.dbPath = str(self.rPath.joinpath('rdf_g.db'))
        self.dbPath = str(self.rPath.joinpath('rdf_bsddb'))

        self.dbUri = Literal(f"sqlite:///{self.dbPath}")
        self.cid = None

        self.sCidChanged = AsyncSignal(str, str)

    @property
    def xmlExportUrl(self):
        return f'file:///{self.xmlExportPath}'

    async def exportTtl(self):
        await asyncWriteFile(
            str(self.exportsPath.joinpath('export.ttl')),
            await self.ttlize()
        )

    async def exportXml(self):
        await asyncWriteFile(
            str(self.exportsPath.joinpath('export.ttl')),
            await self.xmlize()
        )
        # self.serialize(str(self.xmlExportPath), format='xml')

    def _serial(self, fmt):
        buff = io.BytesIO()
        self.serialize(buff, format=fmt)
        buff.seek(0, 0)
        return buff.getvalue()

    async def ttlize(self):
        return await self.loop.run_in_executor(
            None, self._serial, 'ttl')

    async def xmlize(self):
        return await self.loop.run_in_executor(
            None, self._serial, 'pretty-xml')

    async def ipfsFlush(self, ipfsop, format='xml'):
        export = await self.loop.run_in_executor(
            None, self._serial, format)

        if not export:
            # TODO
            return

        entry = await ipfsop.addBytes(export)
        if entry:
            self.cid = entry['Hash']
            await self.sCidChanged.emit(self.name, self.cid)

    async def mergeFromCid(self, ipfsop, cid, format='xml'):
        try:
            obj = await ipfsop.catObject(cid)
            assert obj is not None
        except Exception as err:
            log.debug(str(err))
        else:
            self.parse(obj, format=format)
