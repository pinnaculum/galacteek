from rdflib import URIRef

from galacteek import AsyncSignal
from galacteek import services
from galacteek.ipfs.pubsub.service import Curve25519JSONPubsubService
from galacteek.ipfs.pubsub.messages.ld import *


class RDFBazaarService(Curve25519JSONPubsubService):
    def __init__(self, *args, **kw):
        super().__init__(*args,
                         runPeriodic=False,
                         peered=True,
                         filterSelfMessages=True, **kw)

        self.sExch = AsyncSignal(RDFGraphsExchangeMessage)
        self.sSparql = AsyncSignal(str, SparQLHeartbeatMessage)

    @property
    def prontoService(self):
        return services.getByDotName('ld.pronto')

    async def processJsonMessage(self, sender, msg, msgDbRecord=None):
        msgType = msg.get('msgtype', None)

        peerCtx = self.ipfsCtx.peers.getByPeerId(sender)
        if not peerCtx:
            self.debug('Message from unauthenticated peer: {}'.format(
                sender))
            return

        if msgType in SparQLHeartbeatMessage.VALID_TYPES:
            await self.handleSparqlMessage(sender, msg, msgDbRecord)

    async def presetMessageForPeer(self, piCtx, message):
        """
        Presets the SmartQL credentials on the heartbeat message

        :rtype: str
        """
        if isinstance(message, SparQLHeartbeatMessage):
            # For every graph, we set the password given by the mw auth

            for graphdef in message.graphs:
                iri = URIRef(graphdef['graphIri'])

                service = self.prontoService.p2pSmartQLServiceByUri(iri)

                if not service:
                    continue

                graphdef['smartqlCredentials'] = {
                    'user': piCtx.peerId,
                    'password': service.mwAuth.passwordForPeer(piCtx.peerId)
                }

        return str(message)

    async def handleSparqlMessage(self, sender, msg, msgDbRecord):
        sMsg = SparQLHeartbeatMessage(msg)

        if sMsg.valid():
            await self.sSparql.emit(sender, sMsg)
