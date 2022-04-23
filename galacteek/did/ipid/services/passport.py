import asyncio

from galacteek import services
from galacteek.core import mergeDicts
from galacteek.core import runningApp
from galacteek.core.iphandle import SpaceHandle
from galacteek.did.ipid.services import IPService

from galacteek import GALACTEEK_NAME
from galacteek.ipfs import ipfsOp
from galacteek.ipfs.pubsub.srvs.ipid import IPIDPassportPubsubService

from galacteek.ipfs.pubsub.messages.ipid import *


class DwebPassportService(IPService):
    forTypes = [IPService.SRV_TYPE_PASSPORT]
    endpointName = 'DwebPassport'

    @property
    def pubsubTopic(self):
        return f'{GALACTEEK_NAME}.ipid.{self.ipid.id}.services.passport'

    async def request(self, command='PATCH', **kw):
        body = kw.pop('body', None)

        if not self.ipid.local:
            return

        if command == 'MERGE':
            if not isinstance(body, dict):
                return

            async with self.ipid.editServiceById(self.id) as editor:
                editor.service['serviceEndpoint'] = mergeDicts(
                    editor.service['serviceEndpoint'],
                    body
                )
        elif command == 'VCADD':
            vcid = kw.pop('vcid', None)

            async with self.ipid.editServiceById(self.id) as editor:
                ring = editor.service['serviceEndpoint'].setdefault(
                    'captchaVcRing', [])

                ring.append({
                    '@type': 'VerifiableCredential',
                    '@id': vcid
                })
        elif command == 'VCSETMAIN':
            vcid = body.get('@id', None)
            if not vcid:
                return

            async with self.ipid.editServiceById(self.id) as editor:
                ep = editor.service['serviceEndpoint']

                ep['captchaVc1'] = {
                    '@type': 'VerifiableCredential',
                    '@id': vcid
                }

    async def serviceStart(self):
        self.psPassService = IPIDPassportPubsubService(
            runningApp().ipfsCtx,
            topic=self.pubsubTopic,
            scheduler=runningApp().scheduler,
            filterSelfMessages=True
        )
        await self.pubsubServiceRegister(self.psPassService)

    @ipfsOp
    async def periodicTask(self, ipfsop):
        while True:
            await asyncio.sleep(10)

            psPeers = ipfsop.ctx.pubsub.byTopic('galacteek.peers')

            await psPeers.send(
                IpidServiceExposureMessage.make(
                    self.ipid.did,
                    self.id,
                    self.pubsubTopic,
                    ['captchaChallenge']
                )
            )

    async def onChanged(self):
        pass

    def __str__(self):
        return 'Dweb passport'


async def create(ipid, initialIpHandle: str = None):
    handle = SpaceHandle(initialIpHandle)

    iService = services.getByDotName('dweb.schemes.i')

    iriPassport = iService.iriGenObject('DwebPassport')
    iriPerson = iService.iriGenObject('Person')

    return await ipid.addServiceContexted({
        'id': ipid.didUrl(path='/passport'),
        'type': IPService.SRV_TYPE_PASSPORT
    },
        contextInline=False,
        context='DwebPassport',
        endpoint={
        '@id': iriPassport,
        'me': {
            '@id': iriPerson,
            '@type': 'Person',
            'nickName': handle.username if handle.valid else '',
            'ipHandleShort': handle.human if handle.valid else '',
            'familyName': '',
            'givenName': '',
            'mainLanguage': {
                '@id': 'inter:/rsc/Language/English'
            }
        }
    })
