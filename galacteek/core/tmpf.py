import os.path
import os
import tempfile


class TmpFile:
    def __init__(self, mode='wb', suffix=None, delete=True):
        self._mode = mode
        self._delete = delete
        self._suffix = suffix

    def __enter__(self):
        file_name = os.urandom(24).hex()

        if self._suffix:
            file_name += self._suffix

        file_path = os.path.join(
            tempfile.gettempdir(), file_name)

        open(file_path, "x").close()

        self._tempFile = open(file_path, self._mode)
        return self._tempFile

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._tempFile.close()
        self.remove()

    def remove(self):
        if self._delete:
            os.remove(self._tempFile.name)
