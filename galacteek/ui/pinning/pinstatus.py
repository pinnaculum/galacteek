import asyncio
import time

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QCoreApplication

from PyQt5.QtWidgets import QTreeView
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QHeaderView
from PyQt5.QtWidgets import QToolButton

from PyQt5.QtGui import QStandardItemModel
from PyQt5.QtGui import QBrush
from PyQt5.QtGui import QColor

from galacteek import ensure
from galacteek import partialEnsure

from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.core.modelhelpers import UneditableItem
from galacteek.core.modelhelpers import modelSearch
from galacteek.core.ps import KeyListener
from galacteek.core.ps import makeKeyService
from galacteek.core.asynclib import loopTime

from ..widgets import GalacteekTab
from ..widgets import GMediumToolButton

from ..helpers import messageBox
from ..helpers import getIcon

from .batch import *  # noqa

from ..i18n import iPath
from ..i18n import iCidOrPath
from ..i18n import iUnknown
from ..i18n import iPinned
from ..i18n import iPinning
from ..i18n import iPin
from ..i18n import iCancel
from ..i18n import iInvalidInput


def iQueue():
    return QCoreApplication.translate('PinStatusWidget', 'Queue')


def iStatus():
    return QCoreApplication.translate('PinStatusWidget', 'Status')


def iNodesProcessed():
    return QCoreApplication.translate('PinStatusWidget', 'Nodes')


PinObjectPathRole = Qt.UserRole + 1


class PinStatusWidget(GalacteekTab):
    COL_TS = 0
    COL_QUEUE = 1
    COL_PATH = 2
    COL_STATUS = 3
    COL_PROGRESS = 4
    COL_CTRL = 5

    def __init__(self, gWindow, **kw):
        super(PinStatusWidget, self).__init__(gWindow, **kw)

        self.tree = QTreeView()
        self.tree.setObjectName('pinStatusWidget')
        self.boxLayout = QVBoxLayout()
        self.boxLayout.addWidget(self.tree)

        self.ctrlLayout = QHBoxLayout()
        self.btnPin = QPushButton(iPin())
        self.pathLabel = QLabel(iCidOrPath())
        self.pathEdit = QLineEdit()
        self.ctrlLayout.addWidget(self.pathLabel)
        self.ctrlLayout.addWidget(self.pathEdit)
        self.ctrlLayout.addWidget(self.btnPin)
        self.vLayout.addLayout(self.ctrlLayout)
        self.vLayout.addLayout(self.boxLayout)

        self.app.ipfsCtx.pinItemStatusChanged.connect(self.onPinStatusChanged)
        self.app.ipfsCtx.pinFinished.connect(self.onPinFinished)
        self.app.ipfsCtx.pinItemRemoved.connect(self.onItemRemoved)
        self.pathEdit.returnPressed.connect(self.onPathEntered)
        self.btnPin.clicked.connect(self.onPathEntered)

        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(
            ['TS', iQueue(), iPath(), iStatus(), iNodesProcessed(), ''])

        self.tree.setSortingEnabled(True)
        self.tree.setModel(self.model)
        self.tree.sortByColumn(self.COL_TS, Qt.DescendingOrder)

        for col in [self.COL_QUEUE, self.COL_PATH, self.COL_PROGRESS]:
            self.tree.header().setSectionResizeMode(
                col, QHeaderView.ResizeToContents)

        self.tree.hideColumn(self.COL_TS)

    def resort(self):
        self.model.sort(self.COL_TS, Qt.DescendingOrder)

    def onPathEntered(self):
        text = self.pathEdit.text()
        self.pathEdit.clear()

        path = IPFSPath(text)
        if path.valid:
            ensure(self.app.ipfsCtx.pinner.queue(
                path.objPath, True, None))
        else:
            messageBox(iInvalidInput())

    def removeItem(self, path):
        modelSearch(self.model,
                    search=path, columns=[self.COL_PATH],
                    delete=True)

    def onItemRemoved(self, qname, path):
        self.removeItem(path)

    def getIndexFromPath(self, path):
        idxList = self.model.match(
            self.model.index(0, self.COL_PATH),
            PinObjectPathRole,
            path,
            1,
            Qt.MatchFixedString | Qt.MatchWrap
        )
        if len(idxList) > 0:
            return idxList.pop()

    def findPinItems(self, path):
        idx = self.getIndexFromPath(path)

        if not idx:
            return None

        itemP = self.model.itemFromIndex(idx)

        if not itemP:
            return None

        idxQueue = self.model.index(itemP.row(), self.COL_QUEUE,
                                    itemP.index().parent())
        idxProgress = self.model.index(itemP.row(), self.COL_PROGRESS,
                                       itemP.index().parent())
        idxStatus = self.model.index(itemP.row(), self.COL_STATUS,
                                     itemP.index().parent())
        idxC = self.model.index(itemP.row(), self.COL_CTRL,
                                itemP.index().parent())
        cancelButton = self.tree.indexWidget(idxC)

        return {
            'itemPath': itemP,
            'itemQname': self.model.itemFromIndex(idxQueue),
            'itemProgress': self.model.itemFromIndex(idxProgress),
            'itemStatus': self.model.itemFromIndex(idxStatus),
            'cancelButton': cancelButton
        }

    def updatePinStatus(self, path, status, progress):
        idx = self.getIndexFromPath(path)
        if not idx:
            return

        try:
            itemPath = self.model.itemFromIndex(idx)
            if itemPath and time.time() - itemPath.lastProgressUpdate < 5:
                return

            itemProgress = self.model.itemFromIndex(
                self.model.index(idx.row(), self.COL_PROGRESS, idx.parent())
            )

            itemStatus = self.model.itemFromIndex(
                self.model.index(idx.row(), self.COL_STATUS, idx.parent())
            )

            itemStatus.setText(status)
            itemProgress.setText(progress)
            itemPath.lastProgressUpdate = time.time()
        except:
            pass

    def onPinFinished(self, path):
        items = self.findPinItems(path)

        if items:
            items['itemStatus'].setText(iPinned())
            items['itemProgress'].setText('OK')

            color1 = QBrush(QColor('#4a9ea1'))
            color2 = QBrush(QColor('#66a56e'))

            for item in [items['itemQname'],
                         items['itemPath'], items['itemStatus'],
                         items['itemProgress']]:
                item.setBackground(color1)

            for item in [items['itemStatus'],
                         items['itemProgress']]:
                item.setBackground(color2)

            if items['cancelButton']:
                items['cancelButton'].setEnabled(False)

        self.resort()
        self.purgeFinishedItems()

    def purgeFinishedItems(self):
        maxFinished = 16
        ret = modelSearch(self.model,
                          search=iPinned(),
                          columns=[self.COL_STATUS])

        if len(ret) > maxFinished:
            rows = []
            for idx in ret:
                item = self.model.itemFromIndex(idx)
                if not item:
                    continue
                rows.append(item.row())

            try:
                for row in list(sorted(rows))[int(maxFinished / 2):]:
                    self.model.removeRow(row)
            except:
                pass

    async def onCancel(self, qname, path, *a):
        self.removeItem(path)
        await self.app.ipfsCtx.pinner.cancel(qname, path)

    def onPinStatusChanged(self, qname, path, statusInfo):
        nodesProcessed = statusInfo['status'].get('Progress', iUnknown())

        idx = self.getIndexFromPath(path)

        if not idx:
            # Register it
            btnCancel = QToolButton()
            btnCancel.setIcon(getIcon('cancel.png'))
            btnCancel.setText(iCancel())
            btnCancel.clicked.connect(
                partialEnsure(self.onCancel, qname, path))
            btnCancel.setFixedWidth(140)

            displayPath = path
            if len(displayPath) > 64:
                displayPath = displayPath[0:64] + ' ..'

            itemTs = UneditableItem(str(statusInfo['ts_queued']))
            itemQ = UneditableItem(qname)
            itemP = UneditableItem(displayPath)
            itemP.setData(path, PinObjectPathRole)
            itemP.setToolTip(path)
            itemP.lastProgressUpdate = time.time()

            itemStatus = UneditableItem(iPinning())
            itemProgress = UneditableItem(str(nodesProcessed))

            itemC = UneditableItem('')

            self.model.invisibleRootItem().appendRow(
                [itemTs, itemQ, itemP, itemStatus, itemProgress, itemC])
            idx = self.model.indexFromItem(itemC)
            self.tree.setIndexWidget(idx, btnCancel)
            self.resort()
        else:
            self.updatePinStatus(path, iPinning(), str(nodesProcessed))


RPS_S_QUEUED = 'Queued'
RPS_S_PINNED = 'Pinned'
RPS_S_PINNING = 'Pinning'
RPS_S_FAILED = 'Failed'


class RPSStatusButton(GMediumToolButton, KeyListener):
    """
    Listens to RPS status messages from the pinning service
    """
    psListenKeys = [
        makeKeyService('core', 'pinning')
    ]

    rpsStatus = {}
    lock = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.lock = asyncio.Lock()
        self.setToolTip('No RPS status yet')

    async def event_g_services_core_pinning(self, key, message):
        from galacteek.services.core.pinning.events import RPSEvents

        event = message['event']

        if event['type'] == RPSEvents.ServiceStatusSummary:
            status = event['serviceStatus']

            await self.rpsStatusProcess(status)
        elif event['type'] == RPSEvents.RPSPinningHappening:
            name = event['Name']

            self.app.systemTrayMessage(
                'Remote Pinning',
                f'The content named <b>{name}</b> '
                'is being pinned'
            )

    async def rpsStatusProcess(self, status):
        service = status['Service']
        pinCount = status['Stat'].get('PinCount')

        if not pinCount:
            return

        items = status.get('Items')

        itemsSummary = None
        if items:
            itemsSummary = await self.rpsPinItemsSummary(items)

        async with self.lock:
            data = self.rpsStatus.setdefault(service, {})
            data['pinCount'] = pinCount.copy()
            data['ltLast'] = loopTime()

            await self.updateStatus(itemsSummary)

    async def rpsPinItemsSummary(self, items: list):
        summary = ''
        for item in items:
            status = item.get('Status')

            if status == RPS_S_PINNING.lower():
                summary += '<p>PINNING</p>'

        return summary

    async def updateStatus(self, itemsSummary):
        tooltip = ''
        now = loopTime()

        for service, data in self.rpsStatus.items():
            pinCount = data['pinCount']

            if now - data['ltLast'] > 600:
                # ignore
                tooltip += f'<div>Service {service} inactive</div>'
                continue

            queued = pinCount.get(RPS_S_QUEUED)
            pinned = pinCount.get(RPS_S_PINNED)
            pinning = pinCount.get(RPS_S_PINNING)
            failed = pinCount.get(RPS_S_FAILED)

            if isinstance(pinning, int) and pinning > 0:
                status = iRpcStatusPinning()
            elif isinstance(pinned, int) and pinned > 0:
                status = iRpsStatusPinnedObjCount(pinned)
            else:
                status = iRpsStatusOk()

            if failed and failed > 0:
                status += iRpsStatusSomeFail()

            tooltip += iRpsStatusSummary(
                service,
                status,
                pinned,
                pinning,
                queued,
                failed
            )

        self.setToolTip(tooltip)
