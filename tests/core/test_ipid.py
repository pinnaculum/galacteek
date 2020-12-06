import pytest
import json

from galacteek.did.ipid import IPIDManager
from galacteek.did.ipid.services.videocall import *

from galacteek.did.ipid.services.passport import IPPassportService


class TestIPID:
    @pytest.mark.asyncio
    async def test_creation(self, localipfsop):
        manager = IPIDManager()
        ipid = await manager.create('ipid.test.0')

        assert ipid is not None

    @pytest.mark.asyncio
    async def test_p2pendpoint_explode(self, localipfsop):
        peerId = "12D3KooWD3bfmNbuuuVCYwkjnFt3ukm3qaB3hDED3peHHXawvRAi"
        addr = f"/p2p/{peerId}/x/videocall/room1/1.0.0"
        exploded = localipfsop.p2pEndpointAddrExplode(addr)
        assert exploded is not None

        peerId, protoFull, pVersion = exploded
        assert peerId == peerId
        assert protoFull == '/x/videocall/room1/1.0.0'
        assert pVersion == '1.0.0'

        addr = f"/p2p/{peerId}/x/test"
        exploded = localipfsop.p2pEndpointAddrExplode(addr)
        assert exploded is not None

        assert not localipfsop.p2pEndpointAddrExplode('/p2p/icarus/x/test')
        assert not localipfsop.p2pEndpointAddrExplode(
            f'/p2p/{peerId}/g/test')
        assert not localipfsop.p2pEndpointAddrExplode(
            f'/not/{peerId}/x/test')

    @pytest.mark.asyncio
    async def test_videocall_service(self, localipfsop):
        manager = IPIDManager()
        ipid = await manager.create('ipid.test.1')
        assert ipid is not None

        service = await ipid.addServiceVideoCall('room1')
        print(service)

        # expanded = await service.expandEndpoint()
        q = await service.expandEndpointLdWizard()

        print(q.u('ipschema://galacteek.ld.contexts/DwebVideoCallServiceEndpoint#p2pEndpoint'))
        # print(json.dumps(expanded, indent=4))
        # ipid.dump()

        # await service.ser



    @pytest.mark.asyncio
    async def test_passport_service(self, localipfsop):
        manager = IPIDManager()
        ipid = await manager.create('ipid.test.1')
        assert ipid is not None

        #passport = IPPassportService

        dwebPass = await IPPassportService.addService(ipid)
        print(dwebPass)
