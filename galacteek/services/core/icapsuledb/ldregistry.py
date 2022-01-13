import asyncio
import traceback

from distutils.version import StrictVersion

from galacteek import cached_property
from galacteek.ld.iri import urnParse
from galacteek.ld.sparql import *

from rdflib import URIRef


def parseVersion(v: str):
    try:
        return StrictVersion(v)
    except ValueError:
        return None


def capsuleGenDepends(graph, uri: URIRef):
    try:
        deps = list(graph.objects(
            subject=uri,
            predicate=URIRef('ips://galacteek.ld/ICapsule#depends')
        ))
        assert len(deps) > 0
    except Exception:
        # No deps
        pass
    else:
        for depId in deps:
            try:
                urn = urnParse(str(depId))
                assert urn is not None

                lastp = urn.specific_string.parts[-1]

                v = parseVersion(lastp)

                if not v:
                    # assert v is not None

                    q = urn.rqf_component.query

                    if q:
                        version = q.get('version', None)
                        if version == 'latest':
                            pass

                        if not version:
                            raise ValueError('Invalid version spec')
            except (ValueError, Exception):
                traceback.print_exc()
                continue

            yield {
                'id': str(depId)
            }

            yield from capsuleGenDepends(graph, depId)


class ICRQuerier:
    """
    ICapsules Registry Querier
    """

    def __init__(self, regGraph):
        self.graph = regGraph

    def s(self, *args, **kw):
        s = select(*args, **kw)
        s.add_prefix(
            prefix=Prefix(
                prefix='capsule',
                namespace='ips://galacteek.ld/ICapsule#')
        )
        s.add_prefix(
            prefix=Prefix(
                prefix='comp',
                namespace='ips://galacteek.ld/ICapsuleComponent#')
        )
        s.add_prefix(
            prefix=Prefix(
                prefix='release',
                namespace='ips://galacteek.ld/ICapsuleRelease#')
        )
        s.add_prefix(
            prefix=Prefix(
                prefix='manifest',
                namespace='ips://galacteek.ld/ICapsuleManifest#')
        )
        return s

    @cached_property
    def qAllCapsules(self):
        return self.s(
            vars=['?uri'],
            w=where([
                T(subject='?uri', predicate="a", object="gs:ICapsule")
            ])
        ).get_text()

    @cached_property
    def qLatestCapsuleFromManifest(self):
        return self.s(
            vars=['?latest'],
            w=where([
                T(subject='?manuri', predicate="a",
                  object="gs:ICapsuleManifest"),
                T(subject='?manuri', predicate="manifest:latest",
                  object="?latest"),
            ])
        ).get_text()

    @cached_property
    def qCapsuleComponents(self):
        return self.s(
            vars=['?uri'],
            w=where([
                T(subject='?uri', predicate="a",
                  object="gs:ICapsuleComponent"),
                T(subject='?uri', predicate="comp:icapsule",
                  object="?icapsule")
            ])
        ).get_text()

    @cached_property
    def qAllManifests(self):
        return self.s(
            vars=['?uri', '?description'],
            w=where([
                T(subject='?uri', predicate="a",
                  object="gs:ICapsuleManifest"),
                T(subject='?uri', predicate="manifest:description",
                  object="?description"),
            ])
        ).get_text()

    @cached_property
    def qAllDappManifests(self):
        return self.s(
            vars=['?uri', '?description'],
            w=where([
                T(subject='?uri', predicate="a",
                  object="gs:ICapsuleManifest"),
                T(subject='?uri', predicate="manifest:capsuleType",
                  object='"dapp-qml"'),
                T(subject='?uri', predicate="manifest:description",
                  object="?description"),
            ])
        ).get_text()

    @cached_property
    def qReleaseComponents(self):
        return select(
            vars=['?uri'],
            w=where([
                T(subject='?uri', predicate="a",
                  object="gs:ICapsuleComponent")
            ])
        ).get_text()

    async def capsuleDependencies(self, capsuleUri: URIRef):
        return [d async for d in self.capsuleGenDepends(capsuleUri)]

    async def capsulesList(self):
        return await self.graph.queryAsync(str(self.qAllCapsules))

    async def capsuleManifestsList(self):
        return await self.graph.queryAsync(self.qAllManifests)

    async def latestCapsule(self, manifestUri: URIRef):
        results = list(await self.graph.queryAsync(
            self.qLatestCapsuleFromManifest,
            initBindings={
                'manuri': manifestUri
            }
        ))

        if results:
            return results.pop(0).latest

    async def capsuleComponents(self, capsuleUri: URIRef):
        comps = await self.graph.queryAsync(
            self.qCapsuleComponents,
            initBindings={
                'icapsule': capsuleUri
            }
        )

        return [c.uri for c in comps]

    async def capsuleGenDepends(self, uri: URIRef):
        try:
            manifest = self.graph.value(
                subject=uri,
                predicate=URIRef('ips://galacteek.ld/ICapsule#manifest')
            )
            # assert manifest is not None

            deps = list(self.graph.objects(
                subject=uri,
                predicate=URIRef('ips://galacteek.ld/ICapsule#depends')
            ))
            assert len(deps) > 0
        except Exception:
            # No deps
            pass
        else:
            for depId in deps:
                try:
                    urn = urnParse(str(depId))
                    assert urn is not None

                    lastp = urn.specific_string.parts[-1]
                    q = urn.rqf_component.query

                    v = parseVersion(lastp)

                    if v:
                        yield {
                            'id': str(depId)
                        }

                    elif not v and q and manifest:
                        version = q.get('version', None)
                        if version == 'latest':
                            latest = await self.latestCapsule(
                                manifest)

                            if latest:
                                yield {
                                    'id': latest
                                }
                        else:
                            raise ValueError('Invalid version spec')
                except (ValueError, Exception):
                    continue

                await asyncio.sleep(0)

                async for val in self.capsuleGenDepends(depId):
                    yield val
