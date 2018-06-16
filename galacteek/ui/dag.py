
import json

from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem
from PyQt5.QtCore import Qt, QCoreApplication
from PyQt5.QtGui import QBrush, QColor

from galacteek.appsettings import *
from galacteek.ipfs import cidhelpers
from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.wrappers import ipfsOp, ipfsStatOp
from .helpers import *
from .widgets import GalacteekTab

from . import ui_dagview

def iDagError(path):
    return QCoreApplication.translate('DagViewForm',
            'Error loading the DAG object: {0}').format(path)

class DAGViewer(GalacteekTab):
    def __init__(self, dagHash, *args, **kw):
        super(DAGViewer, self).__init__(*args, **kw)

        self.dagHash = dagHash

        self.ui = ui_dagview.Ui_DagViewForm()
        self.ui.setupUi(self)

        self.ui.dagTree.itemDoubleClicked.connect(self.onItemDoubleClicked)
        self.ui.dagTree.setHeaderLabels(['Key', 'Value'])
        self.ui.dagHash.setText('DAG object: <b>{0}</b>'.format(self.dagHash))
        self.app.task(self.loadDag)

    @ipfsOp
    async def loadDag(self, ipfsop):
        dagNode = await ipfsop.dagGet(self.dagHash)
        if not dagNode:
            return messageBox(iDagError(self.dagHash))
        root = self.ui.dagTree.invisibleRootItem()
        self.displayItem(dagNode, root)
        root.setExpanded(True)
        self.ui.dagTree.resizeColumnToContents(0)

    def onItemDoubleClicked(self, item, col):
        if col == 1:
            text = item.text(col)
            if text.startswith('/ipfs/'):
                self.gWindow.addBrowserTab().browseFsPath(text)
            elif cidhelpers.cidValid(text):
                self.gWindow.addBrowserTab().browseIpfsHash(text)

    def displayItem(self, data, item):
        if data is None:
            return
        if type(data) == dict:
            for dkey, dval in data.items():
                if dkey == '/':
                    # Merkle-link
                    linkValue = str(dval)
                    dictItem = QTreeWidgetItem(item)
                    dictItem.setText(0, 'Merkle link')
                    dictItem.setText(1, linkValue)
                    color = QColor(212, 184, 116)
                    dictItem.setBackground(0, color)
                    dictItem.setBackground(1, color)
                    dictItem.setExpanded(True)
                else:
                    dictItem = QTreeWidgetItem(item)
                    dictItem.setText(0, dkey)
                    dictItem.setExpanded(True)
                    if type(dval) == str:
                        dictItem.setText(1, dval)
                    elif type(dval) == int:
                        dictItem.setText(1, str(dval))
                    else:
                        self.displayItem(dval, dictItem)

        elif type(data) == list:
            for i in range(0, len(data)):
                listItem = QTreeWidgetItem(item)
                listItem.setText(0, "Item {0}".format(i))
                listItem.setExpanded(True)
                self.displayItem(data[i], listItem)
