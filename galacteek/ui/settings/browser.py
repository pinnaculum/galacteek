from . import SettingsFormController


class SettingsController(SettingsFormController):
    configModuleName = 'galacteek.ui.browser'
    qrcIcon = 'network.png'

    @property
    def mapping(self):
        return {
            'galacteek.browser.webprofiles': [
                'defaultWebProfile'
            ],
            'galacteek.ui.browser': [
                ('zoom.default', 'webEngineDefaultZoom')
            ],
            'galacteek.browser': [
                ('qtWebEngine.blink.darkMode', 'useDarkMode'),

                'qtWebEngine.blink.darkModeContrast',
                'qtWebEngine.numRasterThreads',
                'qtWebEngine.ignoreGpuBlacklist',
                'qtWebEngine.enableGpuRasterization',
                'qtWebEngine.enableNativeGpuMemoryBuffers'
            ],
            'galacteek.services.dweb.inter': [
                ('resourceBlocker.enabled', 'enableResourceBlocker')
            ]
        }

    def prepare(self):
        for pName in self.app.availableWebProfilesNames():
            self.ui.defaultWebProfile.insertItem(
                self.ui.defaultWebProfile.count(),
                pName
            )
