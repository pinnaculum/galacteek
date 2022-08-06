import functools

from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QMenu

from galacteek import ensure
from galacteek import partialEnsure
from galacteek import log
from galacteek.ipfs import ipfsOpFn
from galacteek.did.ipid import IPIdentifier
from galacteek.did.ipid import IPService
from galacteek.did.ipid import IPIDServiceException

from .dialogs import GenericTextInputDialog
from .dialogs import HTTPForwardDIDServiceAddDialog
from .helpers import getIcon
from .helpers import runDialog
from .helpers import messageBoxAsync
from .i18n import iOpen
from .i18n import iDelete


class DIDExplorer:
    def __init__(self):
        self.app = QApplication.instance()
        self.app.towers['did'].didServiceOpenRequest.connectTo(
            self.onDidServiceOpen)
        self.app.towers['did'].didServiceObjectOpenRequest.connectTo(
            self.onDidSrvObjectOpen)

    async def onDidSrvObjectOpen(self, did, serviceId, objectId):
        await self.app.resourceOpener.openIpServiceObject(
            serviceId, objectId
        )

    async def onDidServiceOpen(self, did, serviceId, ctx):
        log.debug('Accessing IP Service: {0} (DID: {1})'.format(
            did, serviceId))
        await self.app.resourceOpener.browseIpService(
            serviceId, ctx
        )


def addIpServiceCollection(ipid: IPIdentifier):
    def addService(dlg):
        name = dlg.enteredText()
        if name:
            ensure(ipid.addServiceCollection(name))

    runDialog(
        GenericTextInputDialog, 'Collection name',
        inputRegExp=r'[A-Za-z0-9\-_]+',
        maxLength=24, title='IP collection service',
        accepted=addService
    )


def addHttpForwardService(ipid: IPIdentifier):
    @ipfsOpFn
    async def addHttpService(ipfsop, dlg):
        try:
            url = dlg.getAccessUrl(ipfsop.ctx)

            await ipid.addServiceRaw({
                'id': ipid.didUrl(path=f'/www/{dlg.name}'),
                'type': IPService.SRV_TYPE_HTTP_SERVICE,
                'serviceEndpoint': {
                    '@type': 'HttpForwardServiceEndpoint',
                    '@id': url,

                    'accessUrl': url,
                    'url': url,
                    'httpAdvertisePort': dlg.httpAdvertisePort,
                    'targetMultiAddr': dlg.targetMultiAddr
                }
            })
        except IPIDServiceException as err:
            await messageBoxAsync(str(err))
        except Exception as err:
            await messageBoxAsync(str(err))
        else:
            await ipid.refresh()

    def addService(dlg):
        ensure(addHttpService(dlg))

    runDialog(
        HTTPForwardDIDServiceAddDialog,
        accepted=addService
    )


def addIpServiceVideoCall(ipid: IPIdentifier):
    def addService(dlg):
        name = dlg.enteredText()
        if name:
            ensure(ipid.addServiceVideoCall(name))

    runDialog(
        GenericTextInputDialog, 'Room name',
        inputRegExp=r'[A-Za-z0-9\-_]+',
        maxLength=24, title='Video call service',
        accepted=addService
    )


async def addIpServicesCreationActions(ipid: IPIdentifier,
                                       menu):
    action = QAction(
        getIcon('blocks-cluster.png'),
        'Add collection service',
        menu)

    action.triggered.connect(functools.partial(
        addIpServiceCollection, ipid
    ))

    menu.addAction(action)
    menu.addSeparator()

    action = QAction(
        getIcon('blocks-cluster.png'),
        'Add HTTP forward service',
        menu)

    action.triggered.connect(functools.partial(
        addHttpForwardService, ipid
    ))

    menu.addAction(action)
    menu.addSeparator()


async def deleteIpService(ipid: IPIdentifier, serviceId: str, *args):
    try:
        await ipid.removeServiceById(serviceId)
    except Exception as err:
        await messageBoxAsync(str(err))
    else:
        await messageBoxAsync(f'Service {serviceId}: removed')


async def buildIpServicesMenu(ipid: IPIdentifier,
                              sMenu,
                              parent=None):
    app = QApplication.instance()
    didTower = app.towers['did']

    if ipid.local:
        await addIpServicesCreationActions(ipid, sMenu)

    async for service in ipid.discoverServices():
        if service.type == IPService.SRV_TYPE_COLLECTION:
            menu = QMenu(str(service), sMenu)
            menu.setIcon(getIcon('ipservice.png'))

            async for obj in service.contained():
                action = QAction(
                    getIcon('ipfs-cube-64.png'),
                    obj['name'],
                    menu)
                action.setData({
                    'service': service,
                    'ctx': {
                        'path': obj['path']
                    }
                })

                def emitObjectOpen(tower, did, serviceId, objectId):
                    ensure(tower.didServiceObjectOpenRequest.emit(
                        did, serviceId, objectId
                    ))

                action.triggered.connect(
                    functools.partial(
                        emitObjectOpen, didTower,
                        ipid.did, service.id, obj['id']
                    )
                )

                menu.addAction(action)

            sMenu.addMenu(menu)
        else:
            menu = QMenu(str(service), sMenu)
            menu.setIcon(getIcon('ipservice.png'))

            actionOpen = QAction(
                getIcon('ipservice.png'),
                iOpen(),
                menu)
            actionOpen.setData({
                'service': service,
                'ctx': {}
            })
            actionDelete = QAction(
                getIcon('cancel.png'),
                iDelete(),
                menu)

            if service.type not in [IPService.SRV_TYPE_HTTP_FORWARD_SERVICE,
                                    IPService.SRV_TYPE_HTTP_SERVICE,
                                    IPService.SRV_TYPE_GEMINI_CAPSULE]:
                actionDelete.setEnabled(False)

            menu.addAction(actionOpen)
            menu.addAction(actionDelete)
            sMenu.addMenu(menu)

            def emitOpen(tower, did, serviceId):
                ensure(tower.didServiceOpenRequest.emit(
                    did, serviceId, {})
                )

            actionOpen.triggered.connect(
                functools.partial(emitOpen, didTower, ipid.did, service.id)
            )

            actionDelete.triggered.connect(
                partialEnsure(deleteIpService, ipid, service.id)
            )

            actionOpen.setToolTip(service.id)
            menu.setToolTip(service.id)

    return sMenu


async def buildPublishingMenu(ipid: IPIdentifier, parent=None):
    didPublishMenu = QMenu('DID publish', parent)
    didPublishMenu.setToolTipsVisible(True)
    didPublishMenu.setIcon(getIcon('ipservice.png'))

    async for service in ipid.discoverServices():
        if service.type == IPService.SRV_TYPE_COLLECTION:
            action = QAction(
                getIcon('ipservice.png'),
                str(service),
                didPublishMenu)
            action.setData({
                'service': service,
                'ctx': {}
            })
            didPublishMenu.addAction(action)

    return didPublishMenu
