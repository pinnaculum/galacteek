from galacteek.did.ipid.services import IPService
from galacteek.ld.iri import *


class DwebPassportService(IPService):
    forTypes = [IPService.SRV_TYPE_PASSPORT]
    endpointName = 'DwebPassport'

    def __str__(self):
        return 'Dweb passport'


async def create(ipid):
    iriPassport = objectRandomIri('DwebPassport')
    iriPerson = objectRandomIri('Person')

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
