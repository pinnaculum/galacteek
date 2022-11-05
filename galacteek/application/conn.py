import asyncio

import async_timeout
import traceback

from galacteek import log
from galacteek import logUser

from galacteek.core.profile import UserProfile

from galacteek.ipfs import asyncipfsd
from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.wrappers import *

from galacteek.ui.dwebspace import *

from galacteek.ui.helpers import *
from galacteek.ui.i18n import *
from galacteek.ui.dialogs import IPFSDaemonInitDialog
from galacteek.ui.dialogs import UserProfileInitDialog

from galacteek.appsettings import *


class ApplicationDaemonStarterMixin:
    async def ipfsDaemonInitDialog(self, dlg):
        if self.cmdArgs.configAuto:
            dlg.setDefaultNetwork()
            return dlg.options()

        await runDialogAsync(dlg)

        if dlg.result() == dlg.EXIT_QUIT:
            await self.exitApp()
            return None

        return dlg.options()

    async def startIpfsDaemon(self, migrateRepo=False,
                              config=None,
                              failedReason=None):

        pubsubEnabled = True  # mandatory now ..
        corsEnabled = self.settingsMgr.isTrue(CFG_SECTION_IPFSD,
                                              CFG_KEY_CORS)

        sManager = self.settingsMgr
        section = CFG_SECTION_IPFSD

        # Instantiate an IPFS daemon using asyncipfsd and
        # start it in a task, monitoring the initialization process

        daemonProfiles = []
        dataStore = None

        if self.ipfsd is None:
            # TODO: FFS rewrite the constructor
            self._ipfsd = asyncipfsd.AsyncIPFSDaemon(
                self.ipfsDataLocation,
                goIpfsPath=self.goIpfsBinPath,
                statusPath=self._ipfsdStatusLocation,
                ipfsNetwork=sManager.getSetting(
                    section, CFG_KEY_IPFS_NETWORK_NAME),
                apiport=sManager.getInt(
                    section, CFG_KEY_APIPORT),
                swarmport=sManager.getInt(
                    section, CFG_KEY_SWARMPORT),
                swarmportWs=sManager.getInt(section, CFG_KEY_SWARMPORT_WS),
                swarmportQuic=sManager.getInt(section, CFG_KEY_SWARMPORT_QUIC),
                swarmProtos=sManager.swarmProtosList,
                gatewayport=sManager.getInt(section, CFG_KEY_HTTPGWPORT),
                swarmLowWater=sManager.getInt(section, CFG_KEY_SWARMLOWWATER),
                swarmHighWater=sManager.getInt(
                    section, CFG_KEY_SWARMHIGHWATER),
                storageMax=sManager.getInt(section, CFG_KEY_STORAGEMAX),
                gwWritable=sManager.isTrue(section, CFG_KEY_HTTPGWWRITABLE),
                routingMode=sManager.getSetting(
                    section, CFG_KEY_ROUTINGMODE),
                pubsubRouter=sManager.getSetting(
                    section, CFG_KEY_PUBSUB_ROUTER),
                namesysPubsub=sManager.isTrue(
                    section, CFG_KEY_NAMESYS_PUBSUB),
                pubsubSigning=sManager.isTrue(
                    section, CFG_KEY_PUBSUB_USESIGNING),
                fileStore=sManager.isTrue(section, CFG_KEY_FILESTORE),
                nice=sManager.getInt(section, CFG_KEY_NICE),
                detached=sManager.isTrue(section, CFG_KEY_IPFSD_DETACHED),
                acceleratedDht=sManager.isTrue(section,
                                               CFG_KEY_ACCELERATED_DHT_CLIENT),
                pubsubEnable=pubsubEnabled, corsEnable=corsEnabled,
                migrateRepo=migrateRepo,
                debug=self.cmdArgs.goipfsdebug,
                offline=self.cmdArgs.offline,
                profiles=daemonProfiles,
                dataStore=dataStore,
                loop=self.loop)

        initDialog = IPFSDaemonInitDialog(failedReason=failedReason,
                                          parent=self.mainWindow)

        if self._shuttingDown:
            return

        if (not self.ipfsd.repoExists() or failedReason) and config is None:
            cfg = await self.ipfsDaemonInitDialog(initDialog)
            if not cfg:
                return

            if cfg['daemonType'] == 'custom':
                await self.updateIpfsClient()

                return await self.setupProfileAndRepo()

            try:
                self.ipfsd.dataStore = cfg['dataStore']
                self.ipfsd.profiles = cfg['profiles']
                self.ipfsd.apiport = cfg['apiPort']
                self.ipfsd.swarmport = cfg['swarmPort']
                self.ipfsd.swarmportQuic = cfg['swarmPort']
                self.ipfsd.gatewayport = cfg['gatewayPort']
                self.ipfsd.detached = cfg['keepDaemonRunning']
                self.ipfsd.ipfsNetworkName = cfg.get('ipfsNetworkName', 'main')
            except Exception:
                dataStore = None
                daemonProfiles = []

        ensure(self.startIpfsdTask(self.ipfsd, initDialog))

    @ipfsOp
    async def setupProfileAndRepo(self, ipfsop):
        from galacteek.ipfs import ConnectionError
        try:
            if not await ipfsop.alive():
                raise ConnectionError('Node could not be contacted')

            idx, ws = self.mainWindow.stack.workspaceByName(WS_STATUS)

            await ipfsop.ctx.createRootEntry()

            await self.importCommonResources()

            await self.ipfsCtx.setup(pubsubEnable=True)

            defaultExists = await ipfsop.ctx.defaultProfileExists()

            if not defaultExists:
                while True:
                    dlg = UserProfileInitDialog(
                        automatic=self.cmdArgs.configAuto)

                    if not self.cmdArgs.configAuto:
                        await runDialogAsync(dlg)

                        if not dlg.result() == 1:
                            await messageBoxAsync(
                                'You need to create an identity')
                            continue

                    idx, pDialog = ws.pushProgress('profile')
                    pDialog.spin()
                    pDialog.log('Creating profile and DID ..')

                    try:
                        async for pct, msg in ipfsop.ctx.profileNew(
                            ipfsop,
                            UserProfile.DEFAULT_PROFILE_NAME,
                            initOptions=dlg.options()
                        ):
                            pDialog.log(msg)
                            pDialog.progress(pct)
                    except Exception as err:
                        for z in range(5):
                            pDialog.log(
                                f'Error: {err} (reconfigure in {5-z} secs')
                            await ipfsop.sleep(1)

                        raise err
                    else:
                        break

                    pDialog.stop()
            else:
                idx, pDialog = ws.pushProgress('profile')
                pDialog.spin()
                pDialog.log('Loading profile ..')

                try:
                    async for pct, msg in self.ipfsCtx.profileLoad(
                            ipfsop,
                            UserProfile.DEFAULT_PROFILE_NAME):
                        pDialog.log(msg)
                        pDialog.progress(pct)
                except Exception as err:
                    traceback.print_exc()
                    pDialog.log(f'Error: {err}')
                    return

                pDialog.stop()
                pDialog.log('Ready to roll')
                pDialog.showProgress(False)

            await ipfsop.sleep(0.2)

            ws.clear('profile')

            await self.ipfsCtx.start()
            await self.setupRepository()
        except ConnectionError as err:
            await messageBoxAsync(
                f'IPFS connection error: {err}')
        except RecursionError:
            traceback.print_exc()
        except asyncio.CancelledError:
            return
        except Exception:
            traceback.print_exc()
        else:
            await self.ipfsCtx.ipfsConnectionReady.emit()

    async def startIpfsdTask(self, ipfsd, initDialog):
        from galacteek.ipfs import DaemonStartError

        pDialog = initDialog.progressDialog()
        ipfsd.addMessageCallback(pDialog.log)

        idx, ws = self.mainWindow.stack.workspaceByName(WS_STATUS)
        ws.push(pDialog, 'ipfsd-start')
        pDialog.spin()

        running, client = await ipfsd.loadStatus()
        if running and client:
            log.debug('Daemon was already running')

            self.systemTrayMessage('IPFS', iIpfsDaemonResumed())

            await self.updateIpfsClient(client)
            await ipfsd.peeringConfigure()
            await self.setupProfileAndRepo()
            await self.scheduler.spawn(self.ipfsd.watchProcess())
            await self.ipfsCtx.ipfsDaemonStarted.emit()

            # XXX: emit signal indicating we're reconnecting to this daemon
            ipfsd.publishReconnectingEvent()
            return

        pDialog.log('Starting daemon ...')

        try:
            async for pct, msg in ipfsd.start():
                pDialog.log(msg)
                pDialog.progress(pct)
        except Exception as err:
            pDialog.log(f'Error starting kubo! {err}')

            self.systemTrayMessage('IPFS', iIpfsDaemonProblem())

        running = False

        logUser.info(iIpfsDaemonStarted())

        # Use async_timeout to wait for the
        # proto.eventStarted event to be fired.

        amax, awhile, adead = 28, 12, 22

        for attempt in range(1, amax):
            if attempt in range(0, awhile):
                pDialog.log(iIpfsDaemonWaiting(attempt))

            with async_timeout.timeout(1):
                try:
                    await ipfsd.proto.eventStarted.wait()
                except asyncio.CancelledError:
                    if attempt > awhile:
                        pDialog.showProgress(False)
                        pDialog.showChangeSettings()
                        pDialog.log(iIpfsDaemonTakingAWhile(adead - awhile))

                    if attempt >= adead:
                        break
                    else:
                        continue
                except asyncio.TimeoutError:
                    log.warning(
                        'IPFSD: timeout occured while waiting for '
                        'daemon to start (attempt: {0})'.format(attempt)
                    )
                    continue
                except Exception:
                    running = False
                    raise err
                except DaemonStartError:
                    running = False
                    break
                else:
                    pDialog.log('IPFS daemon is ready!')

                    # Event was set, good to go
                    logUser.info(iIpfsDaemonReady())
                    running = True
                    break

        ipfsd.rmMessageCallback(pDialog.log)
        ws.clear('ipfsd-start')

        if running is True:
            await self.updateIpfsClient()
            await self.ipfsd.peeringConfigure()
            await self.ipfsd.writeStatus()
            await self.setupProfileAndRepo()
            await self.scheduler.spawn(self.ipfsd.watchProcess())
            await self.ipfsCtx.ipfsDaemonStarted.emit()
        else:
            logUser.info(iIpfsDaemonInitProblem())

            try:
                await self.setupIpfsConnection(reconfigure=True)
            except Exception as err:
                log.warning(f'Error setting up connection: {err}')
