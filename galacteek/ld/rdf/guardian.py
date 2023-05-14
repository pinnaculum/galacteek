import attr
import asyncio
import re
import traceback
import json
import time

from rdflib import Graph
from rdflib import URIRef
from rdflib import BNode

from galacteek import log
from galacteek import cached_property

from galacteek.ipfs import ipfsOp
from galacteek.ld.rdf import BaseGraph


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

    async def processLikeAction(self, src: Graph, dst: Graph, s, p, o):
        lpred = URIRef('ips://galacteek.ld/likes')

        liked = src.value(
            subject=s,
            predicate=URIRef('ips://galacteek.ld/object')
        )
        agent = src.value(
            subject=s,
            predicate=URIRef('ips://galacteek.ld/agent')
        )

        # Like it or not, you'll only ever like it once
        dst.remove((
            agent,
            lpred,
            liked
        ))

        dst.add((
            agent,
            lpred,
            liked
        ))

    async def processGenericReaction(self, src: Graph, dst: Graph,
                                     s: URIRef, p: URIRef, o: URIRef):
        """
        Process a ips://galacteek.ld/GenericReaction

        A GenericReaction describes a reaction to a "creative thing"
        (but can be any type of resource)
        """

        reactionId = src.value(
            subject=s,
            predicate=URIRef('ips://galacteek.ld/GenericReaction#reactionId')
        )

        obj = src.value(
            subject=s,
            predicate=URIRef('ips://galacteek.ld/object')
        )
        agent = src.value(
            subject=s,
            predicate=URIRef('ips://galacteek.ld/agent')
        )

        # Purge previous references for this reaction type, leaving us
        # with always only one reaction triple for this agent, reaction
        # type and object, pointing to the latest GenericReaction
        for row in await dst.queryAsync('''
            PREFIX gs: <ips://galacteek.ld/>
            SELECT *
            WHERE {
                ?agent ?reactionId ?reaction .
                ?reaction gs:object ?obj .
            }
            ''', initBindings={
            'agent': agent,
            'obj': obj,
            'reactionId': reactionId
        }):
            dst.remove((
                agent,
                reactionId,
                row['reaction']
            ))

        dst.add((
            agent,
            reactionId,
            s
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

    @ipfsOp
    async def captchaVcProcess(self, ipfsop, src: Graph, dst: Graph, s, p, o):
        issuer = src.value(
            subject=s,
            predicate=URIRef('ips://galacteek.ld/issuer')
        )

        beneficiary = src.value(
            subject=s,
            predicate=URIRef('ips://galacteek.ld/credentialSubject')
        )

        proofuri = src.value(
            subject=s,
            predicate=URIRef('ips://galacteek.ld/proof')
        )

        proof = src.resource(proofuri)

        vmethod = proof.value(
            p=URIRef('ips://galacteek.ld/verificationMethod')
        )

        jws = str(proof.value(
            p=URIRef('ips://galacteek.ld/jws')
        ))

        pem = str(dst.value(
            subject=vmethod,
            predicate=URIRef('https://w3id.org/security#publicKeyPem')
        ))

        rsaAgent = ipfsop.rsaAgent

        key = await rsaAgent.rsaExec.importKey(str(pem))
        if not key:
            return

        payload = await rsaAgent.rsaExec.jwsVerifyFromPem(jws, pem)
        if not payload:
            raise Exception(f'Invalid captcha VC: {s}')

        obj = json.loads(payload)

        if 0:
            dst.add((
                issuer,
                URIRef('ips://galacteek.ld/didCaptchaTrusts'),
                beneficiary
            ))

        dst.remove((
            beneficiary,
            URIRef('ips://galacteek.ld/activeTrustToken'),
            None
        ))

        dst.add((
            beneficiary,
            URIRef('ips://galacteek.ld/activeTrustToken'),
            URIRef(obj.get('id'))
        ))

        return obj


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
        """
        Guardian graph merge

        For each triple, we apply an appropriate action
        (upgrade, trigger, ..).

        Trigger calls a coroutine.
        """

        residue = []

        for s, p, o in graph:
            action = self.decide(dst, s, p, o)

            if action:
                if action.do == 'upgrade':
                    dst.remove((s, p, None))

                elif action.do == 'trigger':
                    try:
                        coro = getattr(action, action.call)
                        assert asyncio.iscoroutinefunction(coro)
                        res = await coro(graph, dst, s, p, o)

                        if isinstance(res, dict):
                            residue.append(res)
                    except Exception as err:
                        log.debug(
                            f'Trigger {action.call} for {s} failed: '
                            f'Error is {err}')
                        traceback.print_exc()
                        continue

            dst.add((s, p, o))
            await asyncio.sleep(0.05)

        return residue

    async def mergeReplace(self,
                           graph: Graph,
                           dst: BaseGraph,
                           notify=True,
                           bnodes=False,
                           debug=False) -> bool:
        """
        Merge the first graph in the second graph

        :param Graph graph: input graph
        :param Graph dst: destination graph
        :param bool notify: Emit PS notify event
        :param bool bnodes: Allow BNodes
        """

        def mergeReplaceRun(gsrc: Graph, gdst: Graph) -> bool:
            try:
                for s, p, o in gsrc:
                    # No BNodes allowed by default
                    if isinstance(s, BNode) and not bnodes:
                        gsrc.remove((s, p, o))
                    elif isinstance(o, BNode) and not bnodes:
                        gsrc.remove((s, p, o))

                    gdst.remove((s, p, None))
                    time.sleep(0.05)

                # Should lock here
                gdst += gsrc
            except Exception:
                log.warning(f'mergeReplace failure ! {traceback.format_exc()}')
                return False
            else:
                # Hub notification

                if notify:
                    dst.publishUpdateEvent(gsrc)

                log.debug(f'mergeReplace success: {len(graph)} triples')
                return True

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, mergeReplaceRun,
                                          graph, dst)
