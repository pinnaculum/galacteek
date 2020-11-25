import asyncio
import os
from functools import partial, partialmethod
from math import floor
from typing import Dict, List, Optional
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtGui import QDropEvent

from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QListWidget
from PyQt5.QtWidgets import QAbstractItemView
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QProgressBar
from PyQt5.QtWidgets import QStyle

from PyQt5.QtWidgets import QTreeWidgetItem
from PyQt5.QtWidgets import QListWidgetItem
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QDialogButtonBox
from PyQt5.QtWidgets import QTreeWidget
from PyQt5.QtWidgets import QToolBar
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QHeaderView
from PyQt5.QtWidgets import QCheckBox

from PyQt5.QtCore import QObject
from PyQt5.QtCore import QSize

from galacteek.core.tmpf import TmpFile
from galacteek.core.tmpf import TmpDir
from galacteek.core.asynclib import partialEnsure
from galacteek.core.asynclib import asyncWriteFile

from galacteek import log
from galacteek import ensure
from galacteek.appsettings import *  # noqa
from galacteek.ipfs import ipfsOp

from galacteek.torrent.control import ControlManager
from galacteek.torrent.control import ControlServer
from galacteek.torrent.control import ControlClient

from galacteek.torrent.models import TorrentState
from galacteek.torrent.models import TorrentInfo
from galacteek.torrent.models import FileTreeNode
from galacteek.torrent.models import FileInfo

from galacteek.torrent.utils import humanize_speed
from galacteek.torrent.utils import humanize_time
from galacteek.torrent.utils import humanize_size

from galacteek.torrent.magnet import IPFSMagnetConvertor
from galacteek.torrent.magnet import isMagnetLink

from galacteek.ui.widgets import GalacteekTab
from galacteek.ui.helpers import getIcon
from galacteek.ui.helpers import getMimeIcon
from galacteek.ui.helpers import runDialogAsync
from galacteek.ui.helpers import inputTextCustom
from galacteek.ui.helpers import questionBoxAsync
from galacteek.ui.helpers import messageBox
from galacteek.ui.helpers import messageBoxAsync
from galacteek.ui.dialogs import TorrentTransferDialog

from galacteek.ui.i18n import iBtAddFromMagnetLink
from galacteek.ui.i18n import iBtAddFromTorrentFile


class TorrentAddingDialog(QDialog):
    SELECTION_LABEL_FORMAT = 'Selected {} files ({})'

    def __init__(
            self,
            parent: QWidget,
            filename: str,
            torrent_info: TorrentInfo,
            control_thread: 'ControlManagerThread'):
        super().__init__(parent)

        self.app = QApplication.instance()

        self._torrent_filepath = Path(filename)

        self._torrent_info = torrent_info
        download_info = torrent_info.download_info
        self._control_thread = control_thread
        self._control = control_thread.control

        vbox = QVBoxLayout(self)

        self._download_dir = self.get_directory(
            self._control.last_download_dir)

        vbox.addWidget(QLabel('Download directory:'))
        vbox.addWidget(self._get_directory_browse_widget())

        vbox.addWidget(QLabel('Announce URLs:'))

        url_tree = QTreeWidget()
        url_tree.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        url_tree.header().close()
        vbox.addWidget(url_tree)
        for i, tier in enumerate(torrent_info.announce_list):
            tier_item = QTreeWidgetItem(url_tree)
            tier_item.setText(0, 'Tier {}'.format(i + 1))
            for url in tier:
                url_item = QTreeWidgetItem(tier_item)
                url_item.setText(0, url)
        url_tree.expandAll()
        vbox.addWidget(url_tree, 1)

        file_tree = QTreeWidget()
        file_tree.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        file_tree.setHeaderLabels(('Name', 'Size'))
        file_tree.header().setSectionResizeMode(
            0, QHeaderView.ResizeToContents)
        self._file_items = []
        self._traverse_file_tree(
            download_info.suggested_name,
            download_info.file_tree,
            file_tree)
        file_tree.sortItems(0, Qt.AscendingOrder)
        file_tree.expandAll()
        file_tree.itemClicked.connect(self._update_checkboxes)
        vbox.addWidget(file_tree, 3)

        self._selection_label = QLabel(
            TorrentAddingDialog.SELECTION_LABEL_FORMAT.format(
                len(download_info.files),
                humanize_size(download_info.total_size)))
        vbox.addWidget(self._selection_label)

        self._ipfsadd_checkbox = QCheckBox(
            'Import files to IPFS when download is complete')
        self._ipfsadd_checkbox.setCheckState(Qt.Unchecked)
        # vbox.addWidget(self._ipfsadd_checkbox)

        self._button_box = QDialogButtonBox(self)
        self._button_box.setOrientation(Qt.Horizontal)
        self._button_box.setStandardButtons(
            QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        self._button_box.button(
            QDialogButtonBox.Ok).clicked.connect(
            self.submit_torrent)
        self._button_box.button(
            QDialogButtonBox.Cancel).clicked.connect(
            self.close)
        vbox.addWidget(self._button_box)

        self.setWindowTitle('Add Torrent')

        self.setMinimumSize(QSize(
            self.app.desktopGeometry.width() / 3,
            (2 * self.app.desktopGeometry.height()) / 3
        ))

    def get_directory(self, directory: Optional[str]):
        dlPath = Path(self.app.settingsMgr.downloadsDir)
        downloadsDir = dlPath.joinpath('torrent')
        return directory if directory is not None else str(downloadsDir)

    def _traverse_file_tree(
            self,
            name: str,
            node: FileTreeNode,
            parent: QWidget):
        item = QTreeWidgetItem(parent)
        item.setCheckState(0, Qt.Checked)
        item.setText(0, name)
        if isinstance(node, FileInfo):
            item.setText(1, humanize_size(node.length))
            item.setIcon(0, getMimeIcon('unknown'))
            self._file_items.append((node, item))
            return

        item.setIcon(0, getIcon('folder-open.png'))
        for name, child in node.items():
            self._traverse_file_tree(name, child, item)

    def _get_directory_browse_widget(self):
        widget = QWidget()
        hbox = QHBoxLayout(widget)
        hbox.setContentsMargins(0, 0, 0, 0)

        self._path_edit = QLineEdit(self._download_dir)
        self._path_edit.setReadOnly(True)
        hbox.addWidget(self._path_edit, 3)

        browse_button = QPushButton('Browse...')
        browse_button.clicked.connect(self._browse)
        hbox.addWidget(browse_button, 1)

        widget.setLayout(hbox)
        return widget

    def _browse(self):
        new_download_dir = QFileDialog.getExistingDirectory(
            self, 'Select download directory', self._download_dir)
        if not new_download_dir:
            return

        self._download_dir = new_download_dir
        self._path_edit.setText(new_download_dir)

    def _set_check_state_to_tree(
            self,
            item: QTreeWidgetItem,
            check_state: Qt.CheckState):
        for i in range(item.childCount()):
            child = item.child(i)
            child.setCheckState(0, check_state)
            self._set_check_state_to_tree(child, check_state)

    def _update_checkboxes(self, item: QTreeWidgetItem, column: int):
        if column != 0:
            return

        new_check_state = item.checkState(0)
        self._set_check_state_to_tree(item, new_check_state)

        while True:
            item = item.parent()
            if item is None:
                break

            has_checked_children = False
            has_partially_checked_children = False
            has_unchecked_children = False
            for i in range(item.childCount()):
                state = item.child(i).checkState(0)
                if state == Qt.Checked:
                    has_checked_children = True
                elif state == Qt.PartiallyChecked:
                    has_partially_checked_children = True
                else:
                    has_unchecked_children = True

            if not has_partially_checked_children and \
                    not has_unchecked_children:
                new_state = Qt.Checked
            elif has_checked_children or has_partially_checked_children:
                new_state = Qt.PartiallyChecked
            else:
                new_state = Qt.Unchecked
            item.setCheckState(0, new_state)

        self._update_selection_label()

    def _update_selection_label(self):
        selected_file_count = 0
        selected_size = 0
        for node, item in self._file_items:
            if item.checkState(0) == Qt.Checked:
                selected_file_count += 1
                selected_size += node.length

        ok_button = self._button_box.button(QDialogButtonBox.Ok)
        if not selected_file_count:
            ok_button.setEnabled(False)
            self._selection_label.setText('Nothing to download')
        else:
            ok_button.setEnabled(True)
            self._selection_label.setText(
                TorrentAddingDialog.SELECTION_LABEL_FORMAT.format(
                    selected_file_count, humanize_size(selected_size)))

    def submit_torrent(self):
        p = Path(self._download_dir)
        try:
            name = self._torrent_filepath.name.replace('.torrent', '')
            pFinal = p.joinpath(name)
            pFinal.mkdir(parents=True, exist_ok=True)
            self._torrent_info.download_dir = str(pFinal)
        except Exception:
            messageBox('Cannot create torrent destination directory')
            return

        self._control.last_download_dir = os.path.abspath(self._download_dir)

        file_paths = []
        for node, item in self._file_items:
            if item.checkState(0) == Qt.Checked:
                file_paths.append(node.path)

        if not self._torrent_info.download_info.single_file_mode:
            self._torrent_info.download_info.select_files(
                file_paths, 'whitelist')

        if self._ipfsadd_checkbox.checkState() == Qt.Checked:
            log.debug('Importing torrent to IPFS when complete')
            self._torrent_info.ipfsImportWhenComplete = True

        self._control_thread.loop.call_soon_threadsafe(
            self._control.add, self._torrent_info)

        self.close()


class TorrentListWidgetItem(QWidget):
    _name_font = QFont()
    _name_font.setBold(True)

    _stats_font = QFont()
    _stats_font.setPointSize(10)

    def __init__(self, control):
        super().__init__()

        self.control = control

        hbox = QHBoxLayout(self)
        vbox = QVBoxLayout()
        hbox.addLayout(vbox)

        self._name_label = QLabel()
        self._name_label.setFont(TorrentListWidgetItem._name_font)
        vbox.addWidget(self._name_label)

        self._upper_status_label = QLabel()
        self._upper_status_label.setFont(TorrentListWidgetItem._stats_font)
        vbox.addWidget(self._upper_status_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(15)
        self._progress_bar.setMaximum(1000)
        vbox.addWidget(self._progress_bar)

        self._lower_status_label = QLabel()
        self._lower_status_label.setFont(TorrentListWidgetItem._stats_font)
        vbox.addWidget(self._lower_status_label)

        self._ipfs_import_button = QPushButton('Import to IPFS')
        self._ipfs_import_button.setVisible(False)
        self._ipfs_import_button.clicked.connect(
            partialEnsure(self.onIpfsImport))
        hbox.addWidget(self._ipfs_import_button)

        self._state = None
        self._waiting_control_action = False

    @property
    def state(self) -> TorrentState:
        return self._state

    @state.setter
    def state(self, state: TorrentState):
        self._state = state
        self._update()

    @property
    def waiting_control_action(self) -> bool:
        return self._waiting_control_action

    @waiting_control_action.setter
    def waiting_control_action(self, value: bool):
        self._waiting_control_action = value
        self._update()

    def _update(self):
        state = self._state

        # FIXME: Avoid XSS in all setText calls
        self._name_label.setText(f'<b>{state.suggested_name}</b>')

        if state.downloaded_size < state.selected_size:
            status_text = '{} of {}'.format(
                humanize_size(
                    state.downloaded_size), humanize_size(
                    state.selected_size))
        else:
            status_text = '{} (complete)'.format(
                humanize_size(state.selected_size))
        status_text += ', Ratio: {:.1f}'.format(state.ratio)
        self._upper_status_label.setText(status_text)

        self._progress_bar.setValue(floor(state.progress * 1000))

        if self.waiting_control_action:
            status_text = 'Waiting'
        elif state.paused:
            status_text = 'Paused'
        elif state.complete:
            self._ipfs_import_button.setVisible(True)

            status_text = 'Uploading to {} of {} peers'.format(
                state.uploading_peer_count, state.total_peer_count)
            if state.upload_speed:
                status_text += ' on {}'.format(
                    humanize_speed(state.upload_speed))
        else:
            status_text = 'Downloading from {} of {} peers'.format(
                state.downloading_peer_count, state.total_peer_count)
            if state.download_speed:
                status_text += ' at {}'.format(
                    humanize_speed(state.download_speed))
            eta_seconds = state.eta_seconds
            if eta_seconds is not None:
                status_text += ', {} remaining'.format(
                    humanize_time(eta_seconds) if
                    eta_seconds is not None else None)
        self._lower_status_label.setText(status_text)

    @ipfsOp
    async def onIpfsImport(self, ipfsop, *a):
        dialog = TorrentTransferDialog(
            self._state.suggested_name,
            self.state.download_dir,
            self.state.info_hash
        )

        await runDialogAsync(dialog)
        if dialog.result() == 1:
            opts = dialog.options()
            self._ipfs_import_button.setEnabled(False)

            if opts['removeTorrent']:
                log.debug(f'Removing torrent {self.state.info_hash}')

                if not self.waiting_control_action:
                    self.waiting_control_action = True

                    await self.control.remove(
                        self.state.info_hash,
                        purgeFiles=True
                    )
        else:
            messageBox('Failed to import files')


class TorrentListWidget(QListWidget):
    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

        self.setAcceptDrops(True)

    def drag_handler(self, event: QDropEvent, drop: bool = False):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.accept()

            if drop:
                self.files_dropped.emit([url.toLocalFile()
                                         for url in event.mimeData().urls()])
        else:
            event.ignore()

    dragEnterEvent = drag_handler
    dragMoveEvent = drag_handler
    dropEvent = partialmethod(drag_handler, drop=True)


class ControlManagerThread(QObject):
    error_happened = pyqtSignal(str, Exception)

    def __init__(self):
        super().__init__()

        self.app = QApplication.instance()
        self._control = ControlManager(self.app._torrentStateLocation)
        self._control_server = ControlServer(self._control, None)
        self._stopping = False
        self._started = False

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        return self.app.loop

    @property
    def control(self) -> ControlManager:
        return self._control

    async def start(self):
        if self._started:
            return

        await self._control.start()
        await self._control_server.start()

        try:
            self._control.load_state()
        except Exception as err:
            self.error_happened.emit('Failed to load program state', err)

        self._control.invoke_state_dumps()

        self._started = True

    async def stop(self):
        await self._control.stop()
        await self._control_server.stop()
        self._started = False


class TorrentClientTab(GalacteekTab):
    def __init__(self, mainWindow):
        super().__init__(mainWindow)

        self.app = QApplication.instance()
        self.ctx.tabIdent = 'btclient'

        control_thread = ControlManagerThread()
        self._control_thread = control_thread
        control = self._control_thread.control
        self.magnetConverter = IPFSMagnetConvertor()

        toolbar = QToolBar()
        self.addToLayout(toolbar)

        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        toolbar.setMovable(False)

        self._add_action = toolbar.addAction(
            getIcon('torrent.png'), iBtAddFromTorrentFile())
        self._add_frommagnet_action = toolbar.addAction(
            getIcon('magnet.png'), iBtAddFromMagnetLink())

        self._add_action.triggered.connect(
            partial(self._add_torrents_triggered))
        self._add_frommagnet_action.triggered.connect(
            partial(self._add_magnet_triggered))

        if not self.magnetConverter.available:
            self._add_frommagnet_action.setEnabled(False)

        self._pause_action = toolbar.addAction(
            self.style().standardIcon(QStyle.SP_MediaPause),
            'Pause')
        self._pause_action.setEnabled(False)
        self._pause_action.triggered.connect(
            partial(self._control_action_triggered, control.pause))

        self._resume_action = toolbar.addAction(getIcon('resume'), 'Resume')
        self._resume_action.setEnabled(False)
        self._resume_action.triggered.connect(
            partial(self._control_action_triggered, control.resume))

        self._remove_action = toolbar.addAction(
            getIcon('clear-all.png'), 'Remove')
        self._remove_action.setEnabled(False)
        self._remove_action.triggered.connect(
            partialEnsure(self._remove_torrent))

        self._list_widget = TorrentListWidget()
        self._list_widget.itemSelectionChanged.connect(
            self._update_control_action_state)
        # self._list_widget.files_dropped.connect(self.add_torrent_files)
        self._torrent_to_item = {}  # type: Dict[bytes, QListWidgetItem]

        self.addToLayout(self._list_widget)

        # control_thread.error_happened.connect(self._error_happened)

        # control.torrents_suggested.connect(self.add_torrent_files)
        control.torrent_added.connect(self._add_torrent_item)
        control.torrent_changed.connect(self._update_torrent_item)
        control.torrent_removed.connect(self._remove_torrent_item)

    async def start(self):
        await self._control_thread.start()

    async def stop(self):
        await self._control_thread.stop()
        self._control_thread = None

    async def onClose(self):
        await self.stop()
        return True

    def _add_torrent_item(self, state: TorrentState):
        widget = TorrentListWidgetItem(self._control_thread.control)
        widget.state = state

        item = QListWidgetItem()
        item.setIcon(getMimeIcon('unknown')
                     if state.single_file_mode else getIcon('folder-open.png'))
        item.setSizeHint(widget.sizeHint())
        item.setData(Qt.UserRole, state.info_hash)

        items_upper = 0
        for i in range(self._list_widget.count()):
            prev_item = self._list_widget.item(i)
            if self._list_widget.itemWidget(
                    prev_item).state.suggested_name > state.suggested_name:
                break
            items_upper += 1
        self._list_widget.insertItem(items_upper, item)

        self._list_widget.setItemWidget(item, widget)
        self._torrent_to_item[state.info_hash] = item

    def _update_torrent_item(self, state: TorrentState):
        if state.info_hash not in self._torrent_to_item:
            return

        widget = self._list_widget.itemWidget(
            self._torrent_to_item[state.info_hash])
        if widget.state.paused != state.paused:
            widget.waiting_control_action = False
        widget.state = state

        self._update_control_action_state()

    async def _remove_torrent(self, *a):
        purgeFiles = await questionBoxAsync(
            'Remove', 'Remove downloaded files ?')

        self._control_action_triggered(
            self._control_thread.control.remove, purgeFiles=purgeFiles)

    def _remove_torrent_item(self, info_hash: bytes):
        item = self._torrent_to_item[info_hash]
        self._list_widget.takeItem(self._list_widget.row(item))
        del self._torrent_to_item[info_hash]

        self._update_control_action_state()

    def _update_control_action_state(self):
        self._pause_action.setEnabled(False)
        self._resume_action.setEnabled(False)
        self._remove_action.setEnabled(False)

        for item in self._list_widget.selectedItems():
            widget = self._list_widget.itemWidget(item)
            if widget.waiting_control_action:
                continue

            if widget.state.paused:
                self._resume_action.setEnabled(True)
            else:
                self._pause_action.setEnabled(True)

            self._remove_action.setEnabled(True)

    def _error_happened(self, description: str, err: Exception):
        QMessageBox.critical(self, description, str(err))

    async def add_torrent_files(self, paths: List[str]):
        for path in paths:
            try:
                torrent_info = TorrentInfo.from_file(path, download_dir=None)
                self._control_thread.control.last_torrent_dir = \
                    os.path.abspath(os.path.dirname(path))

                if torrent_info.download_info.info_hash in \
                        self._torrent_to_item:
                    raise ValueError('This torrent is already added')
            except Exception as err:
                self._error_happened('Failed to add "{}"'.format(path), err)
                continue

            dlg = TorrentAddingDialog(self, path, torrent_info,
                                      self._control_thread)
            await runDialogAsync(dlg)

    @ipfsOp
    async def addTorrentFromIpfs(self, ipfsop, ipfsPath):
        try:
            torrentData = await ipfsop.catObject(str(ipfsPath))

            with TmpFile() as tmpf:
                tmpf.write(torrentData)
                path = tmpf.name

                torrent_info = TorrentInfo.from_file(path, download_dir=None)

                if torrent_info.download_info.info_hash in \
                        self._torrent_to_item:
                    raise ValueError('This torrent is already added')
        except Exception as err:
            self._error_happened('Failed to add "{}"'.format(path), err)
        else:
            dlg = TorrentAddingDialog(self, path, torrent_info,
                                      self._control_thread)
            await runDialogAsync(dlg)

    async def addTorrentFromData(self, filename, data):
        try:
            with TmpDir() as tmpdir:
                tmpPath = Path(tmpdir)
                tPath = tmpPath.joinpath(filename)
                await asyncWriteFile(str(tPath), data)

                torrent_info = TorrentInfo.from_file(
                    str(tPath), download_dir=None)

            if torrent_info.download_info.info_hash in \
                    self._torrent_to_item:
                raise ValueError('This torrent is already added')
        except Exception as err:
            self._error_happened('Failed to add "{}"'.format(path), err)
        else:
            dlg = TorrentAddingDialog(self, str(tPath), torrent_info,
                                      self._control_thread)
            await runDialogAsync(dlg)

    def _add_torrents_triggered(self, *a):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            iBtAddFromTorrentFile(),
            self._control_thread.control.last_torrent_dir,
            'Torrent file (*.torrent);;All files (*)')
        ensure(self.add_torrent_files(paths))

    def _add_magnet_triggered(self, *a):
        if self.magnetConverter.available:
            clipText = self.app.getClipboardText()
            magnetLink = inputTextCustom(
                label=iBtAddFromMagnetLink(),
                text=clipText if isMagnetLink(clipText) else ''
            )

            ensure(self.add_from_magnet(magnetLink))

    async def add_from_magnet(self, magnetLink):
        filename, tData = await self.magnetConverter.toTorrentData(magnetLink)

        if tData:
            await self.addTorrentFromData(filename, tData)
        else:
            await messageBoxAsync(
                'Failed to convert magnet link to torrent')

    @staticmethod
    async def _invoke_control_action(action, info_hash: bytes, **opts):
        try:
            result = action(info_hash, **opts)
            if asyncio.iscoroutine(result):
                await result
        except ValueError:
            pass

    def _control_action_triggered(self, action, **params):
        for item in self._list_widget.selectedItems():
            widget = self._list_widget.itemWidget(item)
            if widget.waiting_control_action:
                continue

            info_hash = item.data(Qt.UserRole)
            asyncio.run_coroutine_threadsafe(
                TorrentClientTab._invoke_control_action(
                    action, info_hash, **params), self._control_thread.loop)

            widget.waiting_control_action = True

        self._update_control_action_state()

    def _show_about(self):
        QMessageBox.about(
            self, 'About', '<p><b>Prototype of a BitTorrent client</b></p>'
            '<p>Copyright &copy; 2016 Alexander Borzunov</p>'
            '<p>Icons are made by Google and Freepik from '
            '<a href="http://www.flaticon.com">www.flaticon.com</a></p>')


def suggest_torrents(manager: ControlManager, filenames: List[str]):
    manager.torrents_suggested.emit(filenames)


async def find_another_daemon(filenames: List[str]) -> bool:
    try:
        async with ControlClient() as client:
            if filenames:
                await client.execute(
                    partial(suggest_torrents, filenames=filenames))
        return True
    except RuntimeError:
        return False
