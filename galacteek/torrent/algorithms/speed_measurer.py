import asyncio
from collections import deque

from galacteek.torrent.models import SessionStatistics
from galacteek.torrent.utils import import_signals


QObject, pyqtSignal = import_signals()


class SpeedMeasurer(QObject):
    if pyqtSignal:
        updated = pyqtSignal()

    def __init__(self, statistics: SessionStatistics):
        super().__init__()

        self._statistics = statistics

    SPEED_MEASUREMENT_PERIOD = 60
    SPEED_UPDATE_TIMEOUT = 2

    assert SPEED_MEASUREMENT_PERIOD % SPEED_UPDATE_TIMEOUT == 0

    async def execute(self):
        max_queue_length = SpeedMeasurer.SPEED_MEASUREMENT_PERIOD // SpeedMeasurer.SPEED_UPDATE_TIMEOUT

        downloaded_queue = deque()
        uploaded_queue = deque()
        while True:
            downloaded_queue.append(self._statistics.downloaded_per_session)
            uploaded_queue.append(self._statistics.uploaded_per_session)

            if len(downloaded_queue) > 1:
                period_in_seconds = (len(downloaded_queue) - 1) * SpeedMeasurer.SPEED_UPDATE_TIMEOUT
                downloaded_per_period = downloaded_queue[-1] - downloaded_queue[0]
                uploaded_per_period = uploaded_queue[-1] - uploaded_queue[0]
                self._statistics.download_speed = downloaded_per_period / period_in_seconds
                self._statistics.upload_speed = uploaded_per_period / period_in_seconds

            if len(downloaded_queue) > max_queue_length:
                downloaded_queue.popleft()
                uploaded_queue.popleft()

            if pyqtSignal:
                self.updated.emit()

            await asyncio.sleep(SpeedMeasurer.SPEED_UPDATE_TIMEOUT)
