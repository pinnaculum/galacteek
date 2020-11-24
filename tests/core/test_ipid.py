import pytest

from galacteek.did.ipid import IPIDManager

from galacteek.did.ipid.services.passport import IPPassportService


class TestIPID:
    @pytest.mark.asyncio
    async def test_creation(self, localipfsop):
        manager = IPIDManager()
        ipid = await manager.create('ipid.test.0')

        assert ipid is not None


    @pytest.mark.asyncio
    async def test_passport_service(self, localipfsop):
        manager = IPIDManager()
        ipid = await manager.create('ipid.test.1')
        assert ipid is not None

        #passport = IPPassportService

        dwebPass = await IPPassportService.addService(ipid)

        print(dwebPass)
