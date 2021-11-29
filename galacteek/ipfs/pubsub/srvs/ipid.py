import secrets
import random
import hashlib
import string
import json

from cachetools import TTLCache

from galacteek.core import captcha3d
from galacteek.core import uid4

from galacteek.did import normedUtcDate

from galacteek.ipfs import ipfsOp
from galacteek.ipfs.pubsub.service import JSONPubsubService
from galacteek.ipfs.pubsub.messages import PubsubMessage
from galacteek.ipfs.pubsub.messages.ipid import *


class PassportCaptchaPSService(JSONPubsubService):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.__capcache = TTLCache(maxsize=16, ttl=60)

    @ipfsOp
    async def processJsonMessage(self, ipfsop, sender, msg, msgDbRecord=None):
        myCtx = self.ipfsCtx.peers.getByPeerId(ipfsop.ctx.node.id)
        peerCtx = self.ipfsCtx.peers.getByPeerId(sender)

        if not peerCtx or not peerCtx.ipid:
            self.debug('Message from unauthenticated peer: {}'.format(
                sender))
            return

        print('ipidpassmsg', str(msg))
        m = PubsubMessage(msg)
        request = m.get('msgtype')
        cached = self.__capcache.get(sender)

        if request == 'captchaChallengeGet':
            if cached:
                capid = cached['id']
                cid = cached['cid']
            else:
                rand = random.Random()
                capid = secrets.token_hex(32)

                captext = ''.join(
                    [str(rand.choice(string.digits)) for x in range(
                        0, rand.randint(4, 7))])
                captcha = captcha3d.generate(captext)
                entry = await ipfsop.addBytes(captcha.getvalue())
                cid = entry['Hash']

                self.__capcache[sender] = {
                    'cid': cid,
                    'answer': captext,
                    'id': capid,
                    'attempts': 0
                }

            await self.send(PubsubMessage({
                'msgtype': 'captchaChallengeSolve',
                'id': capid,
                'captchaCid': cid
            }))

        elif request == 'captchaValidate':
            cached = self.__capcache.get(sender)
            if not cached:
                return

            cached['attempts'] += 1

            answer = m.get('answer')
            capid = m.get('id')

            if answer == cached['answer']:
                # gen signature
                vc = await self.captchaVcGenerate(
                    myCtx.ipid.did,
                    peerCtx.ipid.did
                )

                await self.send(
                    PubsubMessage({
                        'msgtype': 'VcDelivery',
                        'captchaVc': vc
                    })
                )
            else:
                if cached['attempts'] > 2:
                    pass

    @ipfsOp
    async def captchaVcGenerate(self,
                                ipfsop,
                                didIssuer: str,
                                didSubject: str,
                                score=0):
        profile = ipfsop.ctx.currentProfile

        ipid = await profile.userInfo.ipIdentifier()
        rsaAgent = await ipid.rsaAgentGet(ipfsop)

        h = hashlib.sha3_256()
        h.update(didIssuer.encode())
        h.update(didSubject.encode())
        h.update(uid4().encode())

        vcid = f'urn:vc:captcha3auth:{h.hexdigest()}'
        vcproofid = f'{vcid}:proof'
        vcpayloadid = f'{vcid}:payload'
        vcstatusid = f'{vcid}:status'

        jwsToken = await rsaAgent.jwsToken(
            json.dumps({
                '@type': 'OntoloTrustToken',
                'id': vcpayloadid,
                'verifiableCredential': {
                    '@type': 'VerifiableCredential',
                    '@id': vcid
                },
                'holder': {
                    '@type': 'did',
                    '@id': didSubject
                },
                'proof': {
                    '@id': vcproofid
                },
                'score': score
            })
        )

        jwsSerialized = jwsToken.serialize(compact=True)

        return {
            '@id': vcid,
            'type': 'VerifiableCredential',
            'issuer': {
                '@type': 'did',
                '@id': didIssuer
            },
            'issuanceDate': normedUtcDate(),
            # 'expirationDate': normedUtcDate(),
            'credentialSubject': {
                '@type': 'did',
                'id': didSubject
            },
            'credentialStatus': {
                'id': vcstatusid,
                'type': 'CaptchaVcStatus2021'
            },
            'proof': {
                '@id': vcproofid,
                'type': 'RsaSignature2018',
                'created': normedUtcDate(),
                'proofPurpose': 'authentication',
                'verificationMethod': f'{didIssuer}#keys-1',
                # 'challenge': nonce,
                # 'nonce': nonce,
                'jws': jwsSerialized
            }
        }


class IPIDPassportPubsubService(JSONPubsubService):
    @ipfsOp
    async def processJsonMessage(self, ipfsop, sender, msg, msgDbRecord=None):
        peerCtx = self.ipfsCtx.peers.getByPeerId(sender)
        if not peerCtx:
            self.debug('Message from unauthenticated peer: {}'.format(
                sender))
            return

        m = PubsubMessage(msg)
        request = m.get('msgtype')

        if request == 'captchaInit':
            h = hashlib.sha3_256()
            h.update(ipfsop.ctx.node.id.encode())
            h.update(sender.encode())

            topic = f'galacteek.captcha.{h.hexdigest()}'

            srv = PassportCaptchaPSService(
                self.ipfsCtx,
                topic=topic,
                scheduler=self.scheduler,
                metrics=False,
                serveLifetime=120
            )
            self.ipfsCtx.pubsub.reg(srv)
            await srv.startListening()

            await self.send(
                ShortLivedPSChannelMessage.make(
                    topic,
                    'captcha3d/1.0'
                )
            )
