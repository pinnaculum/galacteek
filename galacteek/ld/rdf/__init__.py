import asyncio
import attr
import io
import re
import time
import traceback

from pathlib import Path

from rdflib import RDF
from rdflib import Graph
from rdflib import ConjunctiveGraph
from rdflib import Namespace
from rdflib import URIRef

from galacteek import log
from galacteek import AsyncSignal
from galacteek.ipfs import ipfsOp
from galacteek.core import runningApp
from galacteek.core.asynclib import asyncWriteFile
from galacteek.core.ps import hubLdPublish
from galacteek.core.ps import hubPublish
from galacteek.core.ps import makeKeyService
from galacteek.ld import gLdDefaultContext
from galacteek.ld.iri import urnParse


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


@attr.s(auto_attribs=True)
class GraphUpdateEvent:
    graphUri: str
    srcGraph: Graph
    subjectsUris: list


class GraphURIRef(URIRef):
    """
    Add some methods to analyze the urn associated with the a graph
    """

    @property
    def urn(self):
        return urnParse(str(self))

    @property
    def urnParts(self):
        try:
            return str(self.urn.specific_string).split(':')
        except Exception:
            pass

    @property
    def urnLastPart(self):
        try:
            return self.urnParts[-1]
        except Exception:
            pass

    def specificCut(self, urnBlock: str):
        """
        Return a copy of the URN's specific string stripped of urnBlock
        """
        return re.sub(
            rf'^{urnBlock}', '',
            str(self.urn.specific_string)
        )


class GraphCommonMixin(object):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.loop = asyncio.get_event_loop()
        self.lock = asyncio.Lock()

        self.synchronizer = None
        self.synchronizerSettings: dict = {}
        self._guardian = kw.pop('guardian', None)

    @ property
    def guardian(self):
        return self._guardian

    @ property
    def nameSpaces(self):
        return [n for n in self.iNs.namespaces()]

    def setGuardian(self, g):
        self._guardian = g

    def iNsBind(self):
        # Bind some useful things in the NS manager
        for ns, uri in nsBindings.items():
            if isinstance(uri, list):
                [self.namespace_manager.bind(
                    ns, Namespace(u), override=True) for u in uri]
            else:
                self.namespace_manager.bind(
                    ns, Namespace(uri), override=True)

    def _serial(self, fmt):
        buff = io.BytesIO()
        self.serialize(buff, format=fmt)
        buff.seek(0, 0)
        return buff.getvalue()

    async def rexec(self, fn, *args):
        return await (runningApp()).rexec(fn, self, *args)

    async def ttlize(self):
        return await self.loop.run_in_executor(
            None, self._serial, 'ttl')

    async def ntize(self):
        return await self.loop.run_in_executor(
            None, self._serial, 'nt')

    async def xmlize(self):
        return await self.loop.run_in_executor(
            None, self._serial, 'pretty-xml')

    def queryProcessTime(self, q):
        """
        Run a query on the graph and return the results plus
        the process time spent on the task in nanoseconds

        This is used by the P2P sparql service to do basic rate-limiting
        """

        start_time = time.perf_counter_ns()

        try:
            results = self.query(q)
        except Exception:
            traceback.print_exc()
            return None, None
        else:
            return results, time.perf_counter_ns() - start_time

    async def queryAsync(self, query, initBindings=None):
        def runQuery(q, bindings):
            try:
                return self.query(q, initBindings=bindings)
            except Exception:
                return None

        return await self.loop.run_in_executor(
            runningApp().executor,
            runQuery, query, initBindings
        )

    @ipfsOp
    async def rdfifyObject(self, ipfsop, doc: dict):
        async with ipfsop.ldOps() as ld:
            return await ld.rdfify(doc)

    @ipfsOp
    async def pullObject(self, ipfsop, doc: dict):
        try:
            if '@context' not in doc:
                doc.update(gLdDefaultContext)

            async with ipfsop.ldOps() as ld:
                graph = await ld.rdfify(doc)

            # Could be optimized using another rdflib method
            self.parse(await graph.ttlize(), format='ttl')
        except Exception as err:
            log.debug(f'Error pulling object {doc}: {err}')

    def replace(self, s, p, o):
        self.remove((s, p, None))
        self.add((s, p, o))

    def typesList(self):
        return list(self.subject_objects(RDF.type))

    def publishLdEvent(self, event):
        hubLdPublish(
            makeKeyService('ld', 'pronto'),
            event
        )

    def publishUpdateEvent(self, srcGraph: Graph):
        """
        Publish a graph update notification: this graph
        was updated with the contents of srcGraph
        """

        suris = list(set([str(subj) for subj in srcGraph.subjects()]))

        log.warning(f'Publish GraphUpdateEvent for graph: {self.identifier}')

        self.publishLdEvent({
            'type': 'GraphUpdateEvent',
            'graphUri': str(self.identifier),
            'subjectsUris': suris
        })

        # Post pointer to merged graph as a separate GraphUpdateEvent instance
        hubPublish(
            makeKeyService('ld', 'pronto'),
            GraphUpdateEvent(
                graphUri=str(self.identifier),
                srcGraph=srcGraph,
                subjectsUris=suris
            )
        )


class BaseGraph(GraphCommonMixin, Graph):
    pass


class IGraph(BaseGraph):
    def __init__(self, store,
                 rPath: Path,
                 name: str = None,
                 **kw):
        super(IGraph, self).__init__(store, **kw)

        self.name = name
        self.rPath = rPath
        self.exportsPath = self.rPath.joinpath('exports')
        self.xmlExportPath = self.exportsPath.joinpath('graph.xml')

        self.cid = None

        self.sCidChanged = AsyncSignal(str, str)

    @property
    def xmlExportUrl(self):
        return f'file:///{self.xmlExportPath}'

    async def exportTtl(self):
        self.exportsPath.mkdir(parents=True, exist_ok=True)
        await asyncWriteFile(
            str(self.exportsPath.joinpath('export.ttl')),
            await self.ttlize()
        )

    async def exportXml(self):
        self.exportsPath.mkdir(parents=True, exist_ok=True)
        await asyncWriteFile(
            str(self.exportsPath.joinpath('export.ttl')),
            await self.xmlize()
        )

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


class IConjunctiveGraph(GraphCommonMixin, ConjunctiveGraph):
    pass
