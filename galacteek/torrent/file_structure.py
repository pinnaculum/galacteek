import asyncio
import concurrent.futures
import functools
import os
from bisect import bisect_right
from typing import Iterable, BinaryIO, Tuple

from galacteek.torrent.models import DownloadInfo
from galacteek import log


def delegate_to_executor(func):
    @functools.wraps(func)
    async def wrapper(self: 'FileStructure', *args, acquire_lock=True, **kwargs):
        if acquire_lock:
            await self.lock.acquire()
        try:
            return await self._loop.run_in_executor(
                self.threadpool, functools.partial(func, self, *args, **kwargs))
        except Exception as err:
            log.debug(f'File delegator error: {err}')
            if acquire_lock:
                self.lock.release()
        finally:
            if acquire_lock:
                self.lock.release()

    return wrapper


class OnDemandFile:
    def __init__(self, path, fileinfo, mode='r+b'):
        self._filepath = path
        self._filemode = mode
        self._fileinfo = fileinfo
        self._fd = None

    def __getattr__(self, attr):
        if attr in self.__dict__:
            return getattr(self, attr)

        path = self._filepath
        if not self._fileinfo.selected:
            # log.debug(f'OnDemandFile: {self._fileinfo.path} is not selected')
            path = f'{self._filepath}.bt.discard'

        if attr in ['read', 'write', 'seek', 'close', 'flush']:
            try:
                self.getfd(path)
            except Exception as err:
                log.debug(f'OnDemandFile: error opening file '
                          f'with path: {self._filepath}: {err}')
            else:
                return getattr(self._fd, attr)

    def getfd(self, filepath):
        if not self._fd:
            log.debug(f'OnDemandFile: accessing {filepath}')

            if not os.path.isfile(filepath):
                f = open(filepath, 'w')
                f.close()

            self._fd = open(filepath, self._filemode)
            self._fd.truncate(self._fileinfo.length)

        return self._fd

    def __str__(self):
        return f'OnDemandFile: {self._filepath}'


class FileStructure:
    def __init__(self, download_dir: str, download_info: DownloadInfo):
        self.threadpool = concurrent.futures.ThreadPoolExecutor(max_workers=8)
        self._download_info = download_info

        self._loop = asyncio.get_event_loop()
        self._lock = asyncio.Lock()
        self._descriptors = []
        self._offsets = []
        offset = 0

        try:
            for file in download_info.files:
                path = os.path.join(download_dir, download_info.suggested_name, *file.path)
                directory = os.path.dirname(path)
                if not os.path.isdir(directory):
                    os.makedirs(os.path.normpath(directory))

                f = OnDemandFile(path, file, 'r+b')

                self._descriptors.append(f)
                self._offsets.append(offset)
                offset += file.length
        except (OSError, IOError):
            for f in self._descriptors:
                f.close()
            raise

        self._offsets.append(offset)  # Fake entry for convenience

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock

    def _iter_files(self, offset: int, data_length: int) -> Iterable[Tuple[BinaryIO, int, int]]:
        if offset < 0 or offset + data_length > self._download_info.total_size:
            raise IndexError('Data position out of range')

        # Find rightmost file which start offset less than or equal to `offset`
        index = bisect_right(self._offsets, offset) - 1

        while data_length != 0:
            file_start_offset = self._offsets[index]
            file_end_offset = self._offsets[index + 1]
            file_pos = offset - file_start_offset
            bytes_to_operate = min(file_end_offset - offset, data_length)

            descriptor = self._descriptors[index]

            # log.debug(f'_iter_files({offset}, {data_length}: '
            #           f'{descriptor}, {file_pos}, {bytes_to_operate}')
            yield descriptor, file_pos, bytes_to_operate

            offset += bytes_to_operate
            data_length -= bytes_to_operate
            index += 1

    @delegate_to_executor
    def read(self, offset: int, length: int):
        result = []
        for f, file_pos, bytes_to_operate in self._iter_files(offset, length):
            f.seek(file_pos)
            result.append(f.read(bytes_to_operate))
        return b''.join(result)

    @delegate_to_executor
    def write(self, offset: int, data: memoryview):
        for f, file_pos, bytes_to_operate in self._iter_files(offset, len(data)):
            f.seek(file_pos)
            f.write(data[:bytes_to_operate])

            data = data[bytes_to_operate:]

    @delegate_to_executor
    def flush(self, offset: int, length: int):
        for f, _, _ in self._iter_files(offset, length):
            f.flush()

    def close(self):
        for f in self._descriptors:
            f.close()
