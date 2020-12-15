from mode import Service
from mode.utils.objects import cached_property  # noqa

from galacteek.core import runningApp


class GService(Service):
    def __init__(self, runtimeConfig=None):
        super().__init__()

        self.app = runningApp()
        self.rtCfg = runtimeConfig
