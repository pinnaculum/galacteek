import attr
import os

from galacteek import log
from galacteek.browser.web3channels import Web3Channel
from galacteek.browser.web3channels import Web3Transport

from galacteek.browser import pslisteners
from galacteek.browser.interceptor import IPFSRequestInterceptor

from galacteek.config import cGet
from galacteek.config import DictConfig


qtweFlagsVar = 'QTWEBENGINE_CHROMIUM_FLAGS'


@attr.s(auto_attribs=True)
class BrowserRuntimeObjects:
    web3Transport: Web3Transport = Web3Transport()
    web3Channels: dict = {}
    # XXX
    # web3ContractHandlers = weakref.WeakValueDictionary()
    web3ContractHandlers = dict = {}

    ipfsCeptor: IPFSRequestInterceptor = None

    app: object = None

    def storeContractHandler(self, name, handler):
        self.web3ContractHandlers[name] = handler

    def web3Channel(self, name: str):
        """
        Returns a web3 channel for the given name
        """

        c = self.web3Channels.get(name)
        if not c:
            self.web3Channels[name] = Web3Channel(self.app)
            self.web3Channels[name].moveToThread(self.app.thread())

            log.debug(f'Web3 channel register {name}: '
                      f'{self.web3Channels[name]}')

        return self.web3Channels[name]

    def web3ChannelClone(self, name: str):
        return self.web3Channel(name).clone()


def webEngineSetup(config: DictConfig) -> None:
    """
    Configure QtWebEngine
    """

    flags = []

    mapping = {
        'ignoreGpuBlacklist': '--ignore-gpu-blacklist',
        'enableGpuRasterization':
            '--enable-gpu-rasterization',
        'enableNativeGpuMemoryBuffers':
            '--enable-native-gpu-memory-buffers'
    }

    if config.blink.darkMode is True:
        # Dark mode

        settings = [
            'darkModeEnabled=true',
            'forceDarkModeEnabled=true',
            f'darkModeContrast={config.blink.darkModeContrast}',
            f'darkModePagePolicy={config.blink.darkModePagePolicy}',
            f'darkModeImagePolicy={config.blink.darkModeImagePolicy}',
            'darkModeTextBrightnessThreshold='
            f'{config.blink.darkModeTextBrightnessThreshold}'
        ]

        flags += [
            f"--blink-settings={','.join(settings)}"
        ]

    for key, switch in mapping.items():
        try:
            if getattr(config, key) is True:
                flags.append(switch)
        except Exception:
            continue

    flags += [
        f'--num-raster-threads={config.numRasterThreads}'
    ]

    # Non configurable switches
    flags += [
        '--enable-accelerated-2d-canvas',
        # '--disable-background-timer-throttling',
        '--disable-stack-profiler',
        '--enable-zero-copy',
        '--enable-smooth-scrolling',
        '--enable-accelerated-video-decode'
        # '--default-background-color=000000'
    ]

    os.environ[qtweFlagsVar] = ' '.join(flags)


def onModuleConfigChanged():
    webEngineSetup(cGet('qtWebEngine',
                        mod='galacteek.browser'))


async def browserSetup(app, runtime: BrowserRuntimeObjects) -> None:
    listener = pslisteners.ServicesListener()
    log.debug(f'Services listener: {listener}')

    webEngineSetup(cGet('qtWebEngine'))
