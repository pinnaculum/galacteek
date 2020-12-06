from distutils.version import StrictVersion
from galacteek import log
from galacteek.ipfs import ipfsOp
from galacteek.ipfs.paths import posixIpfsPath
from galacteek.ipfs.regexps import peerIdRe
from galacteek.core import runningApp


def p2pEndpointAddrExplode(addr: str):
    """
    Explode a P2P service endpoint address such as :

    /p2p/12D3KooWD3bfmNbuuuVCYwkjnFt3ukm3qaB3hDED3peHHXawvRAi/x/videocall/room1/1.0.0
    /p2p/12D3KooWD3bfmNbuuuVCYwkjnFt3ukm3qaB3hDED3peHHXawvRAi/x/test

    into its components, returning a tuple in the form

    (peerId, protoFull, protoVersion)

    protoFull can be passed to 'ipfs p2p dial'

    Example:

    ('12D3KooWD3bfmNbuuuVCYwkjnFt3ukm3qaB3hDED3peHHXawvRAi',
     '/x/videocall/room1/1.0.0',
     '1.0.0')

    protoVersion is not mandatory
    """
    parts = addr.lstrip(posixIpfsPath.sep).split(posixIpfsPath.sep)
    try:
        assert parts.pop(0) == 'p2p'
        peerId = parts.pop(0)
        prefix = parts.pop(0)
        assert peerIdRe.match(peerId)
        assert prefix == 'x'

        pVersion = None
        protoA = [prefix]
        protoPart = parts.pop(0)
        protoA.append(protoPart)

        while protoPart:
            try:
                protoPart = parts.pop(0)
            except IndexError:
                break

            protoA.append(protoPart)

            try:
                v = StrictVersion(protoPart)
            except Exception:
                pass
            else:
                # Found a version, should be last element
                pVersion = v
                assert len(parts) == 0
                break

        protoFull = posixIpfsPath.sep + posixIpfsPath.join(*protoA)
        return peerId, protoFull, pVersion
    except Exception:
        log.warning(f'Invalid P2P endpoint address: {addr}')
        return None


def p2pEndpointMake(peerId: str, serviceName: str, protocolVersion='1.0.0'):
    # return f'/p2p/{self.ctx.node.id}/x/{serviceName}/{protocolVersion}'
    return posixIpfsPath.join(
        '/p2p',
        peerId,
        'x',  # default
        serviceName.lstrip('/'),
        protocolVersion
    )


class P2PService:
    def __init__(self, name,
                 description='P2P description',
                 protocolName=None,
                 listenRange=None,
                 listenerClass=None,
                 handler=None, enabled=True, didDefaultRegister=False,
                 protocolVersion=None,
                 setupCtx=None):
        self.app = runningApp()
        self._name = name
        self._description = description
        self._protocolName = protocolName
        self._protocolVersion = protocolVersion
        self._listener = None
        self._listenerClass = listenerClass
        self._listenRange = listenRange if listenRange else \
            ('127.0.0.1', range(49400, 49500))
        self._enabled = enabled
        self._handler = handler
        self._manager = None
        self._setupCtx = setupCtx if setupCtx else {}
        self._didDefaultRegister = didDefaultRegister

    @property
    def name(self):
        return self._name

    @property
    def setupCtx(self):
        return self._setupCtx

    @property
    def didDefaultRegister(self):
        return self._didDefaultRegister

    @property
    def enabled(self):
        return self._enabled

    @property
    def description(self):
        return self._description

    @property
    def protocolName(self):
        return self._protocolName

    @protocolName.setter
    def protocolName(self, p):
        self._protocolName = p

    @property
    def protocolNameFull(self):
        pName = '/x/{0}'.format(self.protocolName)

        if self._protocolVersion:
            pName += '/{self._protocolVersion}'

        return pName

    @property
    def listener(self):
        return self._listener

    @property
    def listenRange(self):
        return self._listenRange

    @listenRange.setter
    def listenRange(self, pr):
        log.debug(f'{self}: Setting listen range: {pr}')
        self._listenRange = pr

    @property
    def handler(self):
        return self._handler

    @property
    def manager(self):
        return self._manager

    @manager.setter
    def manager(self, m):
        self._manager = m

    async def start(self):
        if not self.listener:
            await self.createListener()

    async def stop(self):
        if self.listener:
            await self.listener.close()

    @ipfsOp
    async def createListener(self, ipfsop):
        print('create listener, listener class is', self._listenerClass)
        if self._listenerClass:
            self._listener = self._listenerClass(
                self,
                ipfsop.client,
                self.protocolName,
                self.listenRange,
                None,
                loop=ipfsop.ctx.loop
            )
            addr = await self.listener.open()
            log.debug(
                f'{self}: created listener at address {addr}')
            return addr is not None
        else:
            raise Exception('Implement createListener')

    async def serviceStreams(self):
        # Returns streams associated with this service
        return await self.manager.streamsForProtocol(self.protocolNameFull)

    async def serviceStreamsForRemotePeer(self, peerId):
        # Returns streams associated with this service for a peer
        streams = await self.serviceStreams()
        if streams:
            return [s for s in streams if s['RemotePeer'] == peerId]

    async def didServiceInstall(self, ipid):
        pass


class P2PServiceAutoEndpoint:
    def __init__(self, p2pEndpointAddr):

        pass
