from . import SettingsFormController
from ..helpers import *


class SettingsController(SettingsFormController):
    async def settingsInit(self):
        self.cfgWatch(
            self.ui.downloadsLocation,
            'locations.downloadsPath',
            'galacteek.application'
        )

        self.ui.changeDownloadsPathButton.clicked.connect(
            self.onChangeDownloadsPath)

    def onChangeDownloadsPath(self):
        dirSel = directorySelect()
        if dirSel:
            self.ui.downloadsLocation.setText(dirSel)
