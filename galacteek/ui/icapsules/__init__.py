from rdflib import URIRef

from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QToolButton
from PyQt5.QtWidgets import QListView
from PyQt5.QtWidgets import QLabel

from PyQt5.QtCore import Qt

from galacteek import services
from galacteek import partialEnsure
from galacteek.core import runningApp

from galacteek.core.models.sparql.icapsules import ICapsulesSparQLModel

from ..helpers import getIcon
from ..helpers import messageBoxAsync


class DappsView(QListView):
    def __init__(self, parent=None):
        super(DappsView, self).__init__(parent=parent)

        self.setObjectName('dappsListView')


class ICapsulesManagerWidget(QWidget):
    def __init__(self, parent=None):
        super(ICapsulesManagerWidget, self).__init__(parent=parent)

        self.app = runningApp()
        self.model = ICapsulesSparQLModel(
            graphUri='urn:ipg:icapsules:registries'
        )

        self.vLayout = QVBoxLayout()
        self.setLayout(self.vLayout)

        self.l1 = QLabel(self)
        self.l1.setText('Hello')

        self.listW = DappsView(self)
        self.listW.setModel(self.model)
        self.listW.setViewMode(QListView.IconMode)
        self.listW.doubleClicked.connect(
            partialEnsure(self.onDappDoubleClicked))

        self.vLayout.addWidget(self.listW)

    @property
    def icapsuledb(self):
        return services.getByDotName('core.icapsuledb')

    async def onDappDoubleClicked(self, index):
        muri = self.model.data(index, Qt.DisplayRole)

        if not muri:
            return await messageBoxAsync(
                f'Cannot find latest icapsule for {muri}')

        latest = await self.icapsuledb.querier.latestCapsule(
            muri)

        await self.icapsuledb.profile.installCapsule(
            URIRef(latest))

    def refresh(self):
        self.queryDapps()

    def queryDapps(self):
        print(self.icapsuledb.querier.qAllDappManifests)
        self.model.graphQuery(self.icapsuledb.querier.qAllDappManifests)


class ICapsulesManagerButton(QToolButton):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.app = runningApp()
        self.clicked.connect(self.onOpen)

        self.setIcon(getIcon('capsules/icapsule-green.png'))

    def onOpen(self):
        self.app.mainWindow.wspaceDapps.refresh()
        self.app.mainWindow.wspaceDapps.wsSwitch()
