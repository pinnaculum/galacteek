from math import floor
from typing import Iterable, List, Union

from galacteek.torrent.models import DownloadInfo, TorrentInfo, TorrentState
from galacteek.torrent.utils import humanize_size, humanize_speed, floor_to, humanize_time


COLUMN_WIDTH = 30
INDENT = ' ' * 4
PROGRESS_BAR_WIDTH = 50


def join_lines(lines: Iterable[str]) -> str:
    return ''.join(line[:-1].ljust(COLUMN_WIDTH) if line.endswith('\t') else line for line in lines)


def format_title(info: Union[DownloadInfo, TorrentState], long_format: bool) -> List[str]:
    lines = ['Name: {}\n'.format(info.suggested_name)]
    if long_format:
        lines.append('ID: {}\n'.format(info.info_hash.hex()))
    return lines


def format_content(torrent_info: TorrentInfo) -> List[str]:
    download_info = torrent_info.download_info  # type: DownloadInfo

    lines = ['Announce URLs:\n']
    for i, tier in enumerate(torrent_info.announce_list):
        lines.append(INDENT + 'Tier {}: {}\n'.format(i + 1, ', '.join(tier)))

    total_size_repr = humanize_size(download_info.total_size)
    if download_info.single_file_mode:
        lines.append('Content: single file ({})\n'.format(total_size_repr))
    else:
        lines.append('Content: {} files (total {})\n'.format(len(download_info.files), total_size_repr))
        for file_info in download_info.files:
            lines.append(INDENT + '{} ({})\n'.format('/'.join(file_info.path), humanize_size(file_info.length)))
    return lines


MIN_SPEED_TO_SHOW_ETA = 100 * 2 ** 10  # bytes/s


def format_status(state: TorrentState, long_format: bool) -> List[str]:
    lines = []

    if long_format:
        lines.append('Selected: {}/{} files ({}/{} pieces)\n'.format(
            state.selected_file_count, state.total_file_count, state.selected_piece_count, state.total_piece_count))
        lines.append('Directory: {}\n'.format(state.download_dir))

        if state.paused:
            general_status = 'Paused\n'
        elif state.complete:
            general_status = 'Uploading\n'
        else:
            general_status = 'Downloading\t'
        lines.append('State: ' + general_status)
        if not state.paused and not state.complete:
            eta_seconds = state.eta_seconds
            lines.append('ETA: {}\n'.format(humanize_time(eta_seconds) if eta_seconds is not None else 'unknown'))

        lines.append('Download from: {}/{} peers\t'.format(state.downloading_peer_count, state.total_peer_count))
        lines.append('Upload to: {}/{} peers\n'.format(state.uploading_peer_count, state.total_peer_count))

    lines.append('Download speed: {}\t'.format(
        humanize_speed(state.download_speed) if state.download_speed is not None else 'unknown'))
    lines.append('Upload speed: {}\n'.format(
        humanize_speed(state.upload_speed) if state.upload_speed is not None else 'unknown'))

    lines.append('Size: {}/{}\t'.format(humanize_size(state.downloaded_size), humanize_size(state.selected_size)))
    lines.append('Ratio: {:.1f}\n'.format(state.ratio))

    progress = state.progress
    progress_bar = ('#' * floor(progress * PROGRESS_BAR_WIDTH)).ljust(PROGRESS_BAR_WIDTH)
    lines.append('Progress: {:5.1f}% [{}]\n'.format(floor_to(progress * 100, 1), progress_bar))

    return lines
