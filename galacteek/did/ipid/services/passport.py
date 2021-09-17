from galacteek import services
from galacteek.did.ipid.services import IPService


class DwebPassportService(IPService):
    forTypes = [IPService.SRV_TYPE_PASSPORT]
    endpointName = 'DwebPassport'

    def __str__(self):
        return 'Dweb passport'


async def create(ipid):
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
            'nickName': '',
            'familyName': '',
            'givenName': ''
        }
    })
