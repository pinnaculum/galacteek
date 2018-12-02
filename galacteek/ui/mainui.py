from logbook import Logger, StreamHandler, Handler, StringFormatterHandlerMixin
import os.path
import copy

from PyQt5.QtWidgets import (
    QMainWindow, QDialog,
    QPushButton, QVBoxLayout,
    QToolBar, QMenu, QAction, QActionGroup, QToolButton,
    QTreeView, QHeaderView, QInputDialog, QLabel)
from PyQt5.QtCore import (QCoreApplication, Qt,
                          QTimer, QDateTime)
from PyQt5.Qt import QByteArray, QSizePolicy
from PyQt5 import QtWebEngineWidgets
from PyQt5.QtGui import (QKeySequence,
                         QStandardItemModel,
                         QPixmap,
                         QIcon)

from galacteek import ensure, log
from galacteek.core.glogger import loggerUser, easyFormatString
from galacteek.core.asynclib import asyncify
from galacteek.ui import mediaplayer
from galacteek.ipfs.wrappers import *
from galacteek.ipfs.ipfsops import *
from . import ui_galacteek, ui_ipfsinfos
from . import (browser, files, keys, settings, hashmarks,
               textedit, ipfsview, dag, ipfssearchview, peers, eventlog)
from .helpers import *
from .modelhelpers import *
from .widgets import GalacteekTab
from .dialogs import *
from ..appsettings import *
from .i18n import *


def iHashmarks():
    return QCoreApplication.translate('GalacteekWindow', 'Hashmarks')


def iFileManager():
    return QCoreApplication.translate('GalacteekWindow', 'File Manager')


def iKeys():
    return QCoreApplication.translate('GalacteekWindow', 'IPFS Keys')


def iPinningStatus():
    return QCoreApplication.translate('GalacteekWindow', 'Pinning status')


def iDagViewer():
    return QCoreApplication.translate('GalacteekWindow', 'DAG viewer')


def iEventLog():
    return QCoreApplication.translate('GalacteekWindow', 'Event Log')


def iPeers():
    return QCoreApplication.translate('GalacteekWindow', 'Peers')


def iIpfsSearch(text):
    return QCoreApplication.translate('GalacteekWindow',
                                      'Search: {0}').format(text)


def iFromClipboard(path):
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Clipboard: browse IPFS path: {0}').format(path)


def iClipboardEmpty():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'No valid IPFS CID/path in the clipboard')


def iClipboardClearHistory():
    return QCoreApplication.translate(
        'GalacteekWindow',
        'Clear clipboard history')


def iClipLoaderExplore(path):
    return QCoreApplication.translate('GalacteekWindow',
                                      'Explore IPFS path: {0}').format(path)


def iClipLoaderIpldExplorer(path):
    return QCoreApplication.translate('GalacteekWindow',
                                      'Run IPLD Explorer: {0}').format(path)


def iClipLoaderDagView(path):
    return QCoreApplication.translate('GalacteekWindow',
                                      'DAG view: {0}').format(path)


def iClipboardHistory():
    return QCoreApplication.translate('GalacteekWindow', 'Clipboard history')


def iNewProfile():
    return QCoreApplication.translate('GalacteekWindow', 'New Profile')


def iSwitchedProfile():
    return QCoreApplication.translate('GalacteekWindow',
                                      'Successfully switched profile')


def iClipLoaderBrowse(path):
    return QCoreApplication.translate('GalacteekWindow',
                                      'Browse IPFS path: {0}').format(path)


def iPinningItemStatus(pinPath, pinProgress):
    return QCoreApplication.translate(
        'GalacteekWindow',
        '\nPath: {0}, nodes processed: {1}').format(pinPath, pinProgress)


def iAbout():
    from galacteek import __version__
    return QCoreApplication.translate('GalacteekWindow', '''
        <p><b>Galacteek</b> is a Qt5 based IPFS browser
        </p>
        <p>Author: David Ferlier</p>
        <p>Galacteek version {0}</p>''').format(__version__)


class MainWindowLogHandler(Handler, StringFormatterHandlerMixin):
    def __init__(self, application_name=None, address=None,
                 facility='user', level=0, format_string=None,
                 filter=None, bubble=False, window=None):
        Handler.__init__(self, level, filter, bubble)
        StringFormatterHandlerMixin.__init__(self, format_string)
        self.application_name = application_name
        self.window = window
        self.format_string = easyFormatString

    def emit(self, record):
        self.window.statusMessage(self.format(record))


class IPFSInfosDialog(QDialog):
    def __init__(self, app, parent=None):
        super().__init__(parent)

        self.ui = ui_ipfsinfos.Ui_IPFSInfosDialog()
        self.ui.setupUi(self)
        self.ui.okButton.clicked.connect(lambda: self.done(1))

    @ipfsOp
    async def loadInfos(self, ipfsop):
        try:
            repoStat = await ipfsop.client.repo.stat()
            idInfo = await ipfsop.client.core.id()
        except BaseException:
            for label in [self.ui.repoObjCount,
                          self.ui.repoVersion,
                          self.ui.repoSize,
                          self.ui.repoMaxStorage,
                          self.ui.nodeId,
                          self.ui.agentVersion,
                          self.ui.protocolVersion]:
                label.setText(iUnknown())
        else:
            self.ui.repoObjCount.setText(str(repoStat.get(
                'NumObjects', iUnknown())))
            self.ui.repoVersion.setText(str(repoStat.get(
                'Version', iUnknown())))
            self.ui.repoSize.setText(sizeFormat(repoStat.get(
                'RepoSize', 0)))
            self.ui.repoMaxStorage.setText(sizeFormat(repoStat.get(
                'StorageMax', 0)))

            self.ui.nodeId.setText(idInfo.get('ID', iUnknown()))
            self.ui.agentVersion.setText(idInfo.get(
                'AgentVersion', iUnknown()))
            self.ui.protocolVersion.setText(idInfo.get('ProtocolVersion',
                                                       iUnknown()))


class PinStatusDetails(GalacteekTab):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

        self.tree = QTreeView(self)
        self.vLayout = QVBoxLayout(self)
        self.vLayout.addWidget(self.tree)

        self.app.ipfsCtx.pinItemStatusChanged.connect(self.onPinStatusChanged)
        self.app.ipfsCtx.pinFinished.connect(self.onPinFinished)

        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(
            ['Path', 'Nodes processed'])

        self.tree.setModel(self.model)
        self.tree.header().setSectionResizeMode(0,
                                                QHeaderView.ResizeToContents)

    def findPinItems(self, path):
        ret = modelSearch(self.model,
                          search=path, columns=[0])
        if len(ret) == 0:
            return None, None
        itemP = self.model.itemFromIndex(ret.pop())
        idxS = self.model.index(itemP.row(), 1, itemP.index().parent())
        itemS = self.model.itemFromIndex(idxS)
        return itemP, itemS

    def onPinFinished(self, path):
        ePin, ePinS = self.findPinItems(path)
        if ePinS:
            ePinS.setText(iFinished())

    def onPinStatusChanged(self, path, status):
        nodesProcessed = status.get('Progress', None)
        ePin, ePinS = self.findPinItems(path)

        if not ePin:
            itemP = UneditableItem(path)
            itemS = UneditableItem(str(nodesProcessed) or iUnknown())
            self.model.invisibleRootItem().appendRow(
                [itemP, itemS])
        else:
            if nodesProcessed:
                ePinS.setText(str(nodesProcessed))


class QuickAccessToolBar(QToolBar):
    def __init__(self, window):
        super().__init__()

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.mainW = window

    @ipfsOp
    async def registerFromMarkMeta(self, op, metadata):
        mPath, mark = self.mainW.app.marksLocal.searchByMetadata(metadata)
        if not mark:
            return

        icon = None
        mIcon = mark.get('icon', None)

        if mIcon:
            try:
                iconData = await op.client.cat(mIcon)
                pixmap = QPixmap()
                pixmap.loadFromData(iconData)
                icon = QIcon(pixmap)
            except Exception as e:
                log.debug('Error loading icon {}'.format(e))
                icon = getIcon('unknown-file.png')
            else:
                # Pin the icon since it's valid
                if not await op.isPinned(mIcon):
                    log.debug('Pinning icon {0}'.format(mIcon))
                    await op.ctx.pinner.queue(mIcon, False, None)
        else:
            icon = getIcon('unknown-file.png')

        self.addAction(icon, mark['metadata'].get('title', iUnknown()),
           lambda: self.mainW.addBrowserTab().browseFsPath(mPath))

    async def init(self):
        """
        Add some apps and links to the quickaccess bar
        """

        await self.registerFromMarkMeta({
            'title': 'Hardbin'})
        await self.registerFromMarkMeta({
            'description': 'Distributed wikipedia.*english'})
        await self.registerFromMarkMeta({
            'title': 'IPFessay'})
        await self.registerFromMarkMeta({
            'title': 'IPLD explorer'})


class MainWindow(QMainWindow):
    def __init__(self, app):
        super(MainWindow, self).__init__()

        self.showMaximized()
        self._app = app
        self._allTabs = []
        self._lastFeedMark = None

        self.ui = ui_galacteek.Ui_GalacteekWindow()
        self.ui.setupUi(self)

        loggerUser.handlers.append(
            MainWindowLogHandler(window=self, level='DEBUG'))

        self.tabnFManager = iFileManager()
        self.tabnKeys = iKeys()
        self.tabnPinning = iPinningStatus()
        self.tabnMediaPlayer = iMediaPlayer()

        self.ui.actionQuit.triggered.connect(self.quit)

        self.ui.actionCloseAllTabs.triggered.connect(
            self.onCloseAllTabs)
        self.ui.actionAboutGalacteek.triggered.connect(
            self.onAboutGalacteek)
        self.ui.actionDonate.triggered.connect(
            self.onHelpDonate)
        self.ui.actionSettings.triggered.connect(
            self.onSettings)
        self.ui.actionEvent_log.triggered.connect(
            self.onOpenEventLog)

        self.menuManual = QMenu(iManual())
        self.ui.menuAbout.addMenu(self.menuManual)

        self.ui.myFilesButton.clicked.connect(self.onFileManagerClicked)
        self.ui.myFilesButton.setShortcut(QKeySequence('Ctrl+f'))
        self.ui.manageKeysButton.clicked.connect(self.onIpfsKeysClicked)
        self.ui.openBrowserTabButton.clicked.connect(
            self.onOpenBrowserTabClicked)
        self.ui.hashmarksButton.clicked.connect(self.addHashmarksTab)
        self.ui.hashmarksButton.setShortcut(QKeySequence('Ctrl+m'))
        self.ui.writeNewDocumentButton.clicked.connect(
            self.onWriteNewDocumentClicked)
        self.ui.mediaPlayerButton.clicked.connect(self.onOpenMediaPlayer)
        self.ui.ipfsSearchButton.clicked.connect(self.onIpfsSearch)
        self.ui.ipfsSearch.returnPressed.connect(self.onIpfsSearch)
        self.ui.peersMgrButton.clicked.connect(self.onPeersMgrClicked)

        self.multiLoaderMenu = QMenu()
        self.multiLoaderHMenu = QMenu(iClipboardHistory())
        self.multiLoaderHMenu.triggered.connect(self.onClipboardHistoryMenu)
        self.multiLoadHashAction = QAction(getIconIpfsIce(),
                                           iClipboardEmpty(), self,
                                           shortcut=QKeySequence('Ctrl+o'),
                                           triggered=self.onLoadFromClipboard)
        self.multiExploreHashAction = QAction(
            getIconIpfsIce(),
            iClipboardEmpty(), self,
            shortcut=QKeySequence('Ctrl+e'),
            triggered=self.onExploreFromClipboard)
        self.multiDagViewAction = QAction(
            getIcon('ipld-logo.png'),
            iClipboardEmpty(), self,
            shortcut=QKeySequence('Ctrl+g'),
            triggered=self.onDagViewFromClipboard)
        self.multiIpldExplorerAction = QAction(
            getIcon('ipld-logo.png'),
            iClipboardEmpty(), self,
            shortcut=QKeySequence('Ctrl+i'),
            triggered=self.onIpldExplorerFromClipboard)

        self.multiExploreHashAction.setEnabled(False)
        self.multiLoadHashAction.setEnabled(False)
        self.multiDagViewAction.setEnabled(False)
        self.multiIpldExplorerAction.setEnabled(False)
        self.multiLoaderMenu.addAction(self.multiLoadHashAction)
        self.multiLoaderMenu.addAction(self.multiExploreHashAction)
        self.multiLoaderMenu.addAction(self.multiDagViewAction)
        self.multiLoaderMenu.addAction(self.multiIpldExplorerAction)
        self.multiLoaderMenu.addMenu(self.multiLoaderHMenu)

        self.ui.clipboardMultiLoader.clicked.connect(self.onLoadFromClipboard)
        self.ui.clipboardMultiLoader.setMenu(self.multiLoaderMenu)
        self.ui.clipboardMultiLoader.setToolTip(iClipboardEmpty())
        self.ui.clipboardMultiLoader.setPopupMode(QToolButton.MenuButtonPopup)

        # Global pin-all button
        self.ui.pinAllGlobalButton.setCheckable(True)
        self.ui.pinAllGlobalButton.setAutoRaise(True)
        self.pinAllGlobalChecked = False
        self.ui.pinAllGlobalButton.toggled.connect(self.onToggledPinAllGlobal)

        self.ui.tabWidget.setTabsClosable(True)
        self.ui.tabWidget.tabCloseRequested.connect(self.onTabCloseRequest)
        self.ui.tabWidget.setElideMode(Qt.ElideMiddle)
        self.ui.tabWidget.setUsesScrollButtons(True)

        self.webProfile = QtWebEngineWidgets.QWebEngineProfile.defaultProfile()

        self.ui.menuUser_Profile.addSeparator()
        self.ui.menuUser_Profile.triggered.connect(self.onUserProfile)
        self.ui.actionNew_Profile.setEnabled(False)
        self.profilesActionGroup = QActionGroup(self)

        # Apps/shortcuts toolbar
        self.qaToolbar = QuickAccessToolBar(self)
        self.ui.qaLayout.addWidget(self.qaToolbar)

        # Status bar setup
        self.ui.pinningStatusButton = QPushButton()
        self.ui.pinningStatusButton.setToolTip(iNoStatus())
        self.ui.pinningStatusButton.setIcon(getIcon('pin-black.png'))
        self.ui.pinningStatusButton.clicked.connect(
            self.onPinningStatusDetails)
        self.ui.pubsubStatusButton = QPushButton()
        self.ui.pubsubStatusButton.setIcon(getIcon('network-offline.png'))
        self.ui.ipfsInfosButton = QPushButton()
        self.ui.ipfsInfosButton.setIcon(getIcon('information.png'))
        self.ui.ipfsInfosButton.setToolTip(iIpfsInfos())
        self.ui.ipfsInfosButton.clicked.connect(self.onIpfsInfos)

        self.profileMenu = QMenu()

        self.profileMenu.addAction('View Homepage',
                                   self.onProfileViewHomepage)
        self.profileMenu.addSeparator()
        self.profileMenu.addAction('Post Message',
                                   self.onProfilePostMessage)
        self.ui.profileEditButton.setEnabled(False)
        self.ui.profileEditButton.clicked.connect(self.onProfileEditDialog)
        self.ui.profileEditButton.setPopupMode(QToolButton.MenuButtonPopup)
        self.ui.profileEditButton.setMenu(self.profileMenu)

        self.ui.ipfsStatusLabel = QLabel()
        self.ui.statusbar.addPermanentWidget(self.ui.ipfsStatusLabel)
        self.ui.statusbar.addPermanentWidget(self.ui.ipfsInfosButton)
        self.ui.statusbar.addPermanentWidget(self.ui.pinningStatusButton)
        self.ui.statusbar.addPermanentWidget(self.ui.pubsubStatusButton)

        # Connection status timer
        self.timerStatus = QTimer(self)
        self.timerStatus.timeout.connect(self.onMainTimerStatus)
        self.timerStatus.start(6000)

        self.enableButtons(False)

        # Connect the IPFS context signals
        self.app.ipfsCtx.ipfsConnectionReady.connect(self.onConnReady)
        self.app.ipfsCtx.ipfsRepositoryReady.connect(self.onRepoReady)
        self.app.ipfsCtx.pubsub.psMessageRx.connect(self.onPubsubRx)
        self.app.ipfsCtx.pubsub.psMessageTx.connect(self.onPubsubTx)
        self.app.ipfsCtx.profilesAvailable.connect(self.onProfilesList)
        self.app.ipfsCtx.profileChanged.connect(self.onProfileChanged)
        self.app.ipfsCtx.pinItemStatusChanged.connect(self.onPinStatusChanged)
        self.app.ipfsCtx.pinItemsCount.connect(self.onPinItemsCount)

        # Misc signals
        self.app.marksLocal.feedMarkAdded.connect(self.onFeedMarkAdded)
        self.app.systemTray.messageClicked.connect(self.onSystrayMsgClicked)

        # Application signals
        self.app.clipTracker.clipboardHasIpfs.connect(self.onClipboardIpfs)
        self.app.clipTracker.clipboardHistoryChanged.connect(
            self.onClipboardHistory)
        self.app.manualAvailable.connect(self.onManualAvailable)

        self.ui.tabWidget.removeTab(0)

    @property
    def app(self):
        return self._app

    @property
    def allTabs(self):
        return self._allTabs

    def onOpenEventLog(self):
        self.addEventLogTab(current=True)

    def onProfileEditDialog(self):
        runDialog(ProfileEditDialog, self.app.ipfsCtx.currentProfile,
                  title='Profile Edit dialog')

    @asyncify
    async def onProfileChanged(self, pName, profile):
        if not profile.initialized:
            return

        self.ui.profileEditButton.setEnabled(False)
        await profile.userInfo.loaded
        self.ui.profileEditButton.setEnabled(True)

        for action in self.profilesActionGroup.actions():
            if action.data() == pName:
                action.setChecked(True)
                # Refresh the file manager
                filesM = self.findTabFileManager()
                if filesM:
                    filesM.setupModel()
                    filesM.pathSelectorDefault()

    def onUserProfile(self, action):
        if action is self.ui.actionNew_Profile:
            inText = QInputDialog.getText(self, iNewProfile(),
                                          iNewProfile())
            profile, create = inText
            if create is True and profile:
                self.app.task(self.app.ipfsCtx.profileNew, profile,
                              emitavail=True)
        else:
            pName = action.text()
            if action.isChecked() and \
                    self.app.ipfsCtx.currentProfile.name != pName:
                self.app.ipfsCtx.profileChange(pName)

    def onProfileCreateGPGKey(self):
        pass

    def onProfilePostMessage(self):
        runDialog(ProfilePostMessageDialog, self.app.ipfsCtx.currentProfile)

    def onProfileViewHomepage(self):
        self.addBrowserTab().browseFsPath(os.path.join(
            joinIpns(self.app.ipfsCtx.currentProfile.keyRootId), 'index.html'))

    def onProfilesList(self, pList):
        currentList = [action.data() for action in
                       self.profilesActionGroup.actions()]

        for pName in pList:
            if pName in currentList:
                continue

            action = QAction(self.profilesActionGroup,
                             checkable=True, text=pName)
            action.setData(pName)

        for action in self.profilesActionGroup.actions():
            self.ui.menuUser_Profile.addAction(action)

    def onRepoReady(self):
        self.enableButtons()
        ensure(self.qaToolbar.init())

    def onSystrayMsgClicked(self):
        # Open last shown mark in the systray
        if self._lastFeedMark is not None:
            self.addBrowserTab().browseFsPath(self._lastFeedMark.path)

    def onFeedMarkAdded(self, feedname, mark):
        self._lastFeedMark = mark

        metadata = mark.markData.get('metadata', None)
        if not metadata:
            return

        message = """New entry in IPNS feed {feed}: {title}.
                 Click the message to open it""".format(
            feed=feedname,
            title=metadata['title'] if metadata['title'] else 'No title'
        )

        self.app.systemTrayMessage('IPNS', message, timeout=5000)

    def onIpfsInfos(self):
        dlg = IPFSInfosDialog(self.app)
        dlg.setWindowTitle(iIpfsInfos())
        self.app.task(dlg.loadInfos)
        dlg.exec_()

    def onConnReady(self):
        pass

    def onPubsubRx(self):
        now = QDateTime.currentDateTime()
        self.ui.pubsubStatusButton.setIcon(getIcon('network-transmit.png'))
        self.ui.pubsubStatusButton.setToolTip(
            'Pubsub: last message received {}'.format(now.toString()))

    def onPubsubTx(self):
        pass

    def onPinningStatusDetails(self):
        name = self.tabnPinning
        ft = self.findTabWithName(name)
        if ft:
            return self.ui.tabWidget.setCurrentWidget(ft)
        detailsTab = PinStatusDetails(self)
        self.registerTab(detailsTab, name)

    def updatePinningStatus(self):
        status = copy.copy(self.app.ipfsCtx.pinner.status)
        statusMsg = iItemsInPinningQueue(len(status))

        for pinPath, pinStatus in status.items():
            pinProgress = 'unknown'
            if pinStatus:
                pinProgress = pinStatus.get('Progress', 'unknown')

            statusMsg += iPinningItemStatus(pinPath, pinProgress)

        self.ui.pinningStatusButton.setToolTip(statusMsg)
        self.ui.pinningStatusButton.setStatusTip(statusMsg)

        del status

    def onPinItemsCount(self, count):
        iconLoading = getIcon('pin-blue-loading.png')
        iconNormal = getIcon('pin-black.png')

        if count > 0:
            self.ui.pinningStatusButton.setIcon(iconLoading)
        else:
            self.ui.pinningStatusButton.setIcon(iconNormal)

        self.updatePinningStatus()

    def onPinFinished(self, path):
        self.app.systemTrayMessage('PIN', iPinSuccess(path))

    def onPinStatusChanged(self, path, status):
        self.updatePinningStatus()

    def onManualAvailable(self, lang, entry):
        self.menuManual.addAction(lang, lambda:
                                  self.onOpenManual(lang, entry))

    def onOpenManual(self, lang, docEntry):
        self.addBrowserTab().browseIpfsHash(docEntry['Hash'])

    def enableButtons(self, flag=True):
        for btn in [self.ui.myFilesButton,
                    self.ui.manageKeysButton,
                    self.ui.openBrowserTabButton,
                    self.ui.hashmarksButton,
                    self.ui.mediaPlayerButton,
                    self.ui.writeNewDocumentButton,
                    self.ui.peersMgrButton,
                    self.ui.clipboardMultiLoader]:
            btn.setEnabled(flag)

    def statusMessage(self, msg):
        self.ui.statusbar.showMessage(msg)

    def registerTab(self, tab, name, icon=None, current=False, add=True,
                    tooltip=None):
        idx = None

        if add is True:
            if icon:
                idx = self.ui.tabWidget.addTab(tab, icon, name)
            else:
                idx = self.ui.tabWidget.addTab(tab, name)

        self._allTabs.append(tab)

        if current is True:
            self.ui.tabWidget.setCurrentWidget(tab)

        if tooltip and idx:
            self.ui.tabWidget.setTabToolTip(idx, tooltip)

    def findTabFileManager(self):
        return self.findTabWithName(self.tabnFManager)

    def findTabIndex(self, w):
        return self.ui.tabWidget.indexOf(w)

    def findTabWithName(self, name):
        for idx in range(0, self.ui.tabWidget.count()):
            tName = self.ui.tabWidget.tabText(idx)

            if tName == name:
                return self.ui.tabWidget.widget(idx)

    def removeTabFromWidget(self, w):
        idx = self.ui.tabWidget.indexOf(w)
        if idx:
            self.ui.tabWidget.removeTab(idx)

    def onSettings(self):
        runDialog(settings.SettingsDialog, self.app)

    def onCloseAllTabs(self):
        self.ui.tabWidget.clear()

    def onToggledPinAllGlobal(self, checked):
        self.pinAllGlobalChecked = checked

    def onClipboardHistoryMenu(self, action):
        aData = action.data()

        if aData:
            hItem = aData['item']
            self.addBrowserTab().browseFsPath(hItem['path'])

    def onClipboardHistory(self, history):
        # Called when the clipboard history has changed
        self.multiLoaderHMenu.clear()
        hItems = history.items()

        def onHistoryClear():
            self.app.clipTracker.clearHistory()
            self.onClipboardIpfs(False, None, None)

        self.multiLoaderHMenu.addSeparator()
        self.multiLoaderHMenu.addAction(iClipboardClearHistory(),
                                        lambda: onHistoryClear())

        for hTs, hItem in hItems:
            action = QAction('{0} ({1})'.format(
                hItem['path'],
                hItem['date'].toString()),
                self)
            action.setIcon(getIconIpfsIce())
            action.setData({
                'item': hItem
            })

            self.multiLoaderHMenu.addAction(action)

    def onClipboardIpfs(self, valid, cid, path):
        self.multiExploreHashAction.setEnabled(valid)
        self.multiLoadHashAction.setEnabled(valid)
        self.multiDagViewAction.setEnabled(valid)
        self.multiIpldExplorerAction.setEnabled(valid)
        if valid:
            self.multiExploreHashAction.setText(iClipLoaderExplore(path))
            self.multiLoadHashAction.setText(iClipLoaderBrowse(path))
            self.multiDagViewAction.setText(iClipLoaderDagView(path))
            self.multiIpldExplorerAction.setText(iClipLoaderIpldExplorer(path))
            self.ui.clipboardMultiLoader.setToolTip(iFromClipboard(path))
        else:
            self.multiExploreHashAction.setText(iClipboardEmpty())
            self.multiLoadHashAction.setText(iClipboardEmpty())
            self.multiDagViewAction.setText(iClipboardEmpty())
            self.multiIpldExplorerAction.setText(iClipboardEmpty())
            self.ui.clipboardMultiLoader.setToolTip(iClipboardEmpty())

    def onIpldExplorerFromClipboard(self):
        """
        Open the IPLD explorer application for the CID in the clipboard
        """
        current = self.app.clipTracker.getCurrent()
        if current:
            mPath, mark = self.app.marksLocal.searchByMetadata({
                'title': 'IPLD explorer'})
            if mark:
                link = os.path.join(
                    mPath, '#', 'explore', stripIpfs(current['path']))
                self.addBrowserTab().browseFsPath(link)

    def onLoadFromClipboard(self):
        current = self.app.clipTracker.getCurrent()
        if current:
            self.addBrowserTab().browseFsPath(current['path'])
        else:
            messageBox(iClipboardEmpty())

    def onExploreFromClipboard(self):
        current = self.app.clipTracker.getCurrent()
        if current:
            self.app.task(self.exploreClipboardPath, current['path'])
        else:
            messageBox(iClipboardEmpty())

    def onDagViewFromClipboard(self):
        current = self.app.clipTracker.getCurrent()
        if current:
            view = dag.DAGViewer(current['path'], self)
            self.registerTab(view, iDagViewer(), current=True,
                             icon=getIcon('ipld.png'))
        else:
            messageBox(iClipboardEmpty())

    @ipfsStatOp
    async def exploreClipboardPath(self, ipfsop, path, stat):
        if stat:
            self.exploreHash(stat['Hash'])

    def onAboutGalacteek(self):
        QMessageBox.about(self, 'About Galacteek', iAbout())

    @asyncify
    async def onMainTimerStatus(self):
        @ipfsOpFn
        async def connectionInfo(oper):
            try:
                info = await oper.client.core.id()
            except BaseException:
                return self.ui.ipfsStatusLabel.setText(iErrNoCx())

            nodeId = info.get('ID', iUnknown())
            nodeAgent = info.get('AgentVersion', iUnknownAgent())

            # Get IPFS peers list
            peers = await oper.peersList()
            if not peers:
                return self.ui.ipfsStatusLabel.setText(
                    iCxButNoPeers(nodeId, nodeAgent))

            message = iConnectStatus(nodeId, nodeAgent, len(peers))
            self.ui.ipfsStatusLabel.setText(message)

        await connectionInfo()

    def keyPressEvent(self, event):
        # Ultimately this will be moved to configurable shortcuts
        modifiers = event.modifiers()

        if modifiers & Qt.ControlModifier:
            if event.key() == Qt.Key_T:
                self.addBrowserTab()
            if event.key() == Qt.Key_W:
                idx = self.ui.tabWidget.currentIndex()
                self.onTabCloseRequest(idx)

        super(MainWindow, self).keyPressEvent(event)

    def exploreHash(self, hashV):
        tabName = '... {0}'.format(hashV[2 * int(len(hashV) / 3):])
        tooltip = 'Hash explorer: {0}'.format(hashV)
        view = ipfsview.IPFSHashExplorerToolBox(self, hashV)
        self.registerTab(view, tabName, current=True,
                         icon=getIcon('hash.png'), tooltip=tooltip)

    def addMediaPlayerTab(self):
        name = self.tabnMediaPlayer
        ft = self.findTabWithName(name)
        if ft:
            return ft
        tab = mediaplayer.MediaPlayerTab(self)

        if tab.playerAvailable():
            self.registerTab(tab, name, icon=getIcon('multimedia.png'),
                             current=True)
            return tab
        else:
            messageBox(mediaplayer.iPlayerUnavailable())

    def mediaPlayerQueue(self, path, mediaName=None):
        tab = self.addMediaPlayerTab()
        if tab:
            tab.queueFromPath(path, mediaName=mediaName)

    def mediaPlayerPlay(self, path, mediaName=None):
        tab = self.addMediaPlayerTab()
        if tab:
            tab.playFromPath(path, mediaName=mediaName)

    def addHashmarksTab(self):
        name = iHashmarks()
        ft = self.findTabWithName(name)
        if ft:
            return self.ui.tabWidget.setCurrentWidget(ft)

        tab = hashmarks.HashmarksTab(self)
        self.registerTab(tab, name, current=True,
                         icon=getIcon('hashmarks.png'))

    def onTabCloseRequest(self, idx):
        tab = self.ui.tabWidget.widget(idx)

        if tab not in self.allTabs:
            return False

        if tab.onClose() is True:
            self.ui.tabWidget.removeTab(idx)
            del tab

    def onIpfsSearch(self):
        text = self.ui.ipfsSearch.text()
        self.ui.ipfsSearch.clear()
        if len(text) > 0:
            view = ipfssearchview.IPFSSearchView(text, self)
            self.registerTab(view, iIpfsSearch(text), current=True,
                             icon=getIcon('ipfs-search.png'))

    def onOpenMediaPlayer(self):
        self.addMediaPlayerTab()

    def onOpenBrowserTabClicked(self):
        self.addBrowserTab()

    def onWriteNewDocumentClicked(self):
        w = textedit.AddDocumentWidget(self, parent=self.ui.tabWidget)
        self.registerTab(w, 'New document', current=True)

    def onPeersMgrClicked(self):
        self.showPeersMgr(current=True)

    def onFileManagerClicked(self):
        name = self.tabnFManager

        icon = getIcon('folder-open.png')
        ft = self.findTabWithName(name)
        if ft:
            ft.updateTree()
            return self.ui.tabWidget.setCurrentWidget(ft)

        filesTab = files.FilesTab(self, parent=self.ui.tabWidget)
        self.registerTab(filesTab, name, current=True, icon=icon)

        filesTab.updateTree()

    def onIpfsKeysClicked(self):
        name = self.tabnKeys
        ft = self.findTabWithName(name)
        if ft:
            return self.ui.tabWidget.setCurrentWidget(ft)

        keysTab = keys.KeysTab(self)
        self.registerTab(keysTab, name, current=True)

    def onHelpDonate(self):
        bcAddress = '3HSsNcwzkiWGu6wB18BC6D37JHExpxZvyS'
        runDialog(DonateDialog, bcAddress)

    def addBrowserTab(self, label='No page loaded'):
        icon = getIconIpfsIce()
        tab = browser.BrowserTab(self, parent=self.ui.tabWidget)
        self.ui.tabWidget.addTab(tab, icon, label)
        self.ui.tabWidget.setCurrentWidget(tab)

        mgr = self.app.settingsMgr
        if mgr.isTrue(CFG_SECTION_BROWSER, CFG_KEY_GOTOHOME):
            tab.loadHomePage()

        self.allTabs.append(tab)
        return tab

    def addEventLogTab(self, current=False):
        self.registerTab(eventlog.EventLogWidget(self), iEventLog(),
                         current=current)

    def showPeersMgr(self, current=False):
        # Peers mgr
        name = iPeers()

        ft = self.findTabWithName(name)
        if ft:
            return self.ui.tabWidget.setCurrentWidget(ft)

        pMgr = peers.PeersManager(self, self.app.peersTracker)
        self.registerTab(pMgr, name, current=current)

    def quit(self):
        # Qt and application exit
        ensure(self.app.exitApp())

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.app.systemTrayMessage('Galacteek', iMinimized())
