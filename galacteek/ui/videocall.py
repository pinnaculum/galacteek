import orjson

from galacteek.ipfs import ipfsOp
from galacteek.ipfs.cidhelpers import IPFSPath

from galacteek.ipfs.p2pservices.rendezvous import *
from galacteek.core import runningApp

from .helpers import runDialogAsync
from .dialogs import IPFSCaptchaChallengeDialog
from .dialogs import VideoChatAckWait


class VideoCallInitiator:
    def __init__(self, ipService):
        self.app = runningApp()
        self.ipService  = ipService

    @ipfsOp
    async def start(self, ipfsop):
        await self.videoRendezVous(ipfsop)

    async def videoRendezVous(self, ipfsop):
        remotePeerId, serviceName = ipfsop.p2pEndpointExplode(
            self.ipService.endpoint)

        req = {
            'peer': ipfsop.ctx.node.id
        }

        try:
            async with ipfsop.p2pDialer(
                    remotePeerId, serviceName,
                    addressAuto=True) as sCtx:
                if sCtx.failed:
                    raise Exception(f'Cannot reach {remotePeerId}')

                async with sCtx.session.ws_connect(
                    sCtx.httpUrl('/rendezVousWs')) as ws:

                    await self.rendezVousMain(ipfsop, ws)
        except Exception as err:
            print(str(err))
            return None

    async def rendezVousMain(self, ipfsop, ws):
        await ws.send_json({
            'msgtype': 'init',
            'peer': ipfsop.ctx.node.id
        })

        await ipfsop.sleep()
        ackWaitWidget = VideoChatAckWait()

        #msg = await ws.receive_json()
        async for rawmsg in ws:
            try:
                msg = orjson.loads(rawmsg.data)
            except Exception:
                continue

            print(msg)
            if msg['msgtype'] == MSGTYPE_CAPTCHA_CHALLENGE:
                await ipfsop.sleep()

                sessionId = msg.get(MSGF_SESSIONID)
                captchaCid = msg.get(MSGF_CAPTCHACID)

                captchaRaw = await ipfsop.catObject(captchaCid)

                if not captchaRaw:
                    raise Exception(f'ERR: {captchaCid}')

                for att in range(8):
                    dlg = IPFSCaptchaChallengeDialog(captchaRaw)
                    await runDialogAsync(dlg)

                    if dlg.result() == 1 and dlg.inputText:
                        print(dlg.inputText)
                        await ws.send_json({
                            'msgtype': MSGTYPE_CAPTCHA_SOLVE,
                            MSGF_SESSIONID: msg[MSGF_SESSIONID],
                            'peer': ipfsop.ctx.node.id,
                            MSGF_CAPTCHA: dlg.inputText
                        })
                        break

            elif msg['msgtype'] == MSGTYPE_ACKWAIT:
                #await runDialogAsync(dlg)
                ackWaitWidget.show()

            elif msg['msgtype'] == MSGTYPE_RENDEZVOUS:
                ackWaitWidget.hide()
                rvTopic = msg.get(MSGF_RVTOPIC)
                print(rvTopic)

                await self.startVideoCall(rvTopic)

    @ipfsOp
    async def startVideoCall(self, ipfsop, rvTopic):
        rootPath = IPFSPath(ipfsop.ctx.resources['videocall']['Hash'])
        offerPath = rootPath.child('offer.html')
        offerPath.fragment = rvTopic

        tab = self.app.mainWindow.addBrowserTab()
        tab.browseFsPath(offerPath)
