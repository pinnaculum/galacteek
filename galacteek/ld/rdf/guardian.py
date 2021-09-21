import attr
import asyncio
import re

from rdflib import Graph
from rdflib import URIRef

from galacteek import cached_property


@attr.s(auto_attribs=True)
class GuardianAction:
    do: str = 'nothing'
    action: dict = {}


@attr.s(auto_attribs=True)
class GuardianUpgradeAction:
    do: str = 'upgrade'


@attr.s(auto_attribs=True)
class GuardianTriggerAction:
    do: str = 'trigger'
    call: str = None

    async def followSubject(self, src: Graph, dst: Graph, s, p, o):
        followee = src.value(
            subject=s,
            predicate=URIRef('ips://galacteek.ld/followee')
        )
        agent = src.value(
            subject=s,
            predicate=URIRef('ips://galacteek.ld/agent')
        )

        dst.add((
            agent,
            URIRef('ips://galacteek.ld/follows'),
            followee
        ))

    async def unfollowSubject(self, src: Graph, dst: Graph, s, p, o):
        followee = src.value(
            subject=s,
            predicate=URIRef('ips://galacteek.ld/followee')
        )
        agent = src.value(
            subject=s,
            predicate=URIRef('ips://galacteek.ld/agent')
        )

        if followee and agent:
            dst.remove((
                agent,
                URIRef('ips://galacteek.ld/follows'),
                followee
            ))


@attr.s(auto_attribs=True)
class TriplesUpgradeRule:
    priority: int = 0
    subject: str = ''
    predicate: str = ''
    object: str = ''
    action: dict = {}

    @cached_property
    def a(self):
        try:
            do = self.action.get('do', None)
            if do == 'upgrade':
                return GuardianUpgradeAction(**self.action)
            elif do == 'trigger':
                return GuardianTriggerAction(**self.action)
        except Exception:
            return GuardianAction()

    @cached_property
    def reSub(self):
        return re.compile(self.subject)

    @cached_property
    def rePredicate(self):
        return re.compile(self.predicate)

    @cached_property
    def reObject(self):
        return re.compile(self.object)


class GraphGuardian:
    def __init__(self, uri, cfg):
        self.uri = uri
        self.cfg = cfg
        self.tUpRules = []

    def configure(self):
        uprules = self.cfg.get('rules', [])

        # Triples upgrade rules
        for rdef in uprules:
            try:
                assert rdef['subject'] is not None
                rule = TriplesUpgradeRule(**rdef)
            except Exception:
                continue
            else:
                self.tUpRules.append(rule)

        return True

    def decide(self, graph, subject: URIRef,
               predicate, obj):
        action = None
        for rule in self.tUpRules:
            if rule.reSub.match(str(subject)):
                ma_p = rule.rePredicate.match(str(predicate))
                ma_o = rule.reObject.match(str(obj))

                if ma_p and ma_o:
                    action = rule.a
                    break

        return action

    async def merge(self, graph: Graph, dst: Graph):
        for s, p, o in graph:
            action = self.decide(dst, s, p, o)

            if action:
                if action.do == 'upgrade':
                    dst.remove((s, p, None))

                elif action.do == 'trigger':
                    try:
                        coro = getattr(action, action.call)
                        assert asyncio.iscoroutinefunction(coro)
                        await coro(graph, dst, s, p, o)
                    except Exception:
                        pass

            # print('===>', s, p, o)
            dst.add((s, p, o))
