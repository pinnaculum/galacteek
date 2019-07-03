import pytest
import aioipfs

from galacteek.core import glogger
from galacteek.ipfs.ipfsops import IPFSOperator
from galacteek.ipfs.ipfsops import IPFSOpRegistry


glogger.basicConfig(level='DEBUG')


@pytest.fixture
def localipfsclient():
    client = aioipfs.AsyncIPFS(host='127.0.0.1', port=5001)
    yield client


@pytest.fixture(scope='session')
def localipfsop(localipfsclient):
    op = IPFSOperator(localipfsclient)
    IPFSOpRegistry.regDefault(op)
    yield op
