from rdflib import URIRef

from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QFormLayout
from PyQt5.QtWidgets import QAbstractItemView

from PyQt5.QtCore import QRegExp
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QUrl
from PyQt5.QtCore import QSortFilterProxyModel

from PyQt5.QtGui import QRegExpValidator

from galacteek import ensure
from galacteek import partialEnsure
from galacteek import database
from galacteek import services

from galacteek.core.ipfsmarks import *
from galacteek.core.iptags import ipTagsFormat

from galacteek.core.models.sparql.tags import TagsSparQLModel
from galacteek.core.models.sparql import SubjectUriRole

from galacteek.browser.schemes import isEnsUrl
from galacteek.browser.schemes import isHttpUrl
from galacteek.browser.schemes import isGeminiUrl

from galacteek.ipfs import cidhelpers
from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.wrappers import ipfsOp
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.appsettings import *

from galacteek.ld.rdf import hashmarks as rdf_hashmarks
from galacteek.ld.rdf import GraphURIRef

from ..forms import ui_addhashmarkdialog
from ..forms import ui_iptagsmanager

from ..helpers import *
from ..widgets import ImageWidget
from ..widgets import IconSelector
from ..widgets import ImageSelector
from ..widgets import OutputGraphSelectorWidget

from ..i18n import iDoNotPin
from ..i18n import iPinSingle
from ..i18n import iPinRecursive
from ..i18n import iNoTitleProvided
from ..i18n import iNoCategory
from ..i18n import iHashmarkIPTagsEdit

from ..i18n import iAddHashmark
from ..i18n import iEditHashmark

from ..i18n import iPublicHashmarks
from ..i18n import iPrivateHashmarks


def boldLabelStyle():
    return 'QLabel { font-weight: bold; }'


class AddHashmarkDialog(QDialog):
    def __init__(
            self,
            resourceUrl: str,
            title: str,
            description: str,
            pin=False,
            pinRecursive=False,
            schemePreferred=None,
            parent=None):
        super().__init__(parent)

        self.app = QApplication.instance()
        self.hashmark = None  # previous hashmark

        self.resourceUriRef = URIRef(resourceUrl)
        self.ipfsPath = IPFSPath(resourceUrl)
        self.mimeType = None
        self.filesStat = None

        self.iconCid = None
        self.schemePreferred = schemePreferred

        self.ui = ui_addhashmarkdialog.Ui_AddHashmarkDialog()
        self.ui.setupUi(self)
        self.ui.resourceLabel.setText(self.resourceUrl)
        self.ui.resourceLabel.setStyleSheet(boldLabelStyle())
        self.ui.resourceLabel.setToolTip(self.resourceUrl)
        self.ui.newCategory.textChanged.connect(self.onNewCatChanged)
        self.ui.title.setText(title)

        # pix = QPixmap.fromImage(QImage(':/share/icons/hashmarks.png'))
        # pix = pix.scaledToWidth(32)
        # self.ui.hashmarksIconLabel.setPixmap(pix)

        self.iconWidget = None

        self.ui.pinCombo.addItem(iDoNotPin())
        self.ui.pinCombo.addItem(iPinSingle())
        self.ui.pinCombo.addItem(iPinRecursive())

        self.ui.formLayout.setRowWrapPolicy(QFormLayout.DontWrapRows)
        self.ui.formLayout.setFieldGrowthPolicy(
            QFormLayout.ExpandingFieldsGrow)
        self.ui.formLayout.setLabelAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.ui.formLayout.setHorizontalSpacing(20)

        self.graphSelector = OutputGraphSelectorWidget(
            uriFilters=[
                r'urn:ipg:i:love:hashmarks:(private|public.*|search.*)'
            ],
            parent=self
        )
        self.graphSelector.graphUriSelected.connect(self.onOutGraphSelect)

        self.ui.gSelectorLayout.addWidget(self.graphSelector)

        # Add icon selector
        self.iconSelector = IconSelector(parent=self, allowEmpty=True)
        self.iconSelector.iconSelected.connect(self.onIconSelected)
        self.iconSelector.emptyIconSelected.connect(self.onIconEmpty)
        self.ui.formLayout.insertRow(7, QLabel('Icon'),
                                     self.iconSelector)

        # Img
        self.imageSelector = ImageSelector(parent=self)

        self.ui.formLayout.insertRow(8, QLabel('Thumbnail'),
                                     self.imageSelector)

        regexp1 = QRegExp(r"[A-Za-z0-9/\-]+")  # noqa
        self.ui.newCategory.setValidator(QRegExpValidator(regexp1))
        self.ui.newCategory.setMaxLength(64)

        if pin is True:
            self.ui.pinCombo.setCurrentIndex(1)
        elif pinRecursive is True:
            self.ui.pinCombo.setCurrentIndex(2)

        if isinstance(description, str):
            self.ui.description.insertPlainText(description)

        self.ui.groupBox.setProperty('niceBox', True)
        self.app.repolishWidget(self.ui.groupBox)

        ensure(self.scan())

    @property
    def resourceUrl(self):
        return str(self.resourceUriRef)

    @property
    def graphUri(self):
        return self.graphSelector.graphUri

    def onOutGraphSelect(self, graphUri: GraphURIRef):
        msg, ico = None, None

        if graphUri.urnLastPart:
            print(graphUri.urnLastPart)
            if graphUri.urnLastPart == 'private':
                msg = iPrivateHashmarks(str(graphUri))
                ico = ':/share/icons/key-diago.png'

            elif graphUri.urnLastPart.startswith('search'):
                msg = 'Search room'  # TODO
            elif graphUri.urnLastPart.startswith('public'):
                msg = iPublicHashmarks(str(graphUri))
        if msg:
            self.ui.outputGraphMessage.setText(f'<b>{msg}</b>')

        if ico:
            pix = QPixmap.fromImage(QImage(ico))
            pix = pix.scaledToWidth(32)
            self.graphSelector.iconLabel.setPixmap(pix)
        else:
            self.graphSelector.iconLabel.clear()

    @ipfsOp
    async def getHashmark(self, ipfsop):
        # TODO: need to use ipfsUriRef of the resource uri ref if non ipfs
        # would be nice to have a class that can handle IPFSPath or QUrl

        if self.ipfsPath.valid:
            return await rdf_hashmarks.getLdHashmark(self.ipfsPath.ipfsUriRef)
        else:
            return await rdf_hashmarks.getLdHashmark(self.resourceUriRef)

    @ipfsOp
    async def scan(self, ipfsop):
        self.hashmark = await self.getHashmark()

        if self.hashmark is None:
            self.ui.groupBox.setTitle(iAddHashmark())
        else:
            self.ui.groupBox.setTitle(iEditHashmark())

            self.ui.title.setText(self.hashmark['title'])
            self.ui.description.setPlainText(self.hashmark['descr'])
            self.ui.comment.setText(self.hashmark['comment'])

            # Icon
            if self.hashmark['iconUrl']:
                path = IPFSPath.fromUriRef(self.hashmark['iconUrl'])
                icon = await getIconFromIpfs(ipfsop, path.objPath)

                if icon:
                    cid = await path.resolve(ipfsop)

                    self.iconSelector.injectCustomIcon(
                        icon, cid, path.ipfsUrl
                    )

        if self.ipfsPath.valid and self.ipfsPath.isIpfs:
            # Only for /ipfs/ (immutable)
            # TODO: check for non-unixfs objects

            self.mimeType, self.filesStat = await self.app.rscAnalyzer(
                self.ipfsPath,
                statType=['files']
            )

    @ipfsOp
    async def initDialog(self, ipfsop):
        # await self.fillCategories()

        if not self.ipfsPath.valid:
            # TODO: rename self.resourceUrl
            # Handle HTTP/ENS URLs

            url = QUrl(self.resourceUrl)
            if isHttpUrl(url) or isEnsUrl(url) or isGeminiUrl(url):
                self.ui.pinCombo.setEnabled(False)

            if isHttpUrl(url):
                ensure(self.fetchFavIcon(url))

    @ipfsOp
    async def fetchFavIcon(self, ipfsop, qurl):
        qurl.setPath('/favicon.ico')

        try:
            async with self.app.webClientSession() as session:
                _data = bytearray()

                async with session.get(qurl.toString()) as resp:
                    while True:
                        b = await resp.content.read(1024)
                        if not b:
                            break

                        _data.extend(b)
                        if len(_data) > 512 * 1024:
                            raise Exception('Too large, get lost')

                icon = getIconFromImageData(_data)
                if not icon:
                    raise Exception('Invalid .ico')

                entry = await ipfsop.addBytes(_data)
                if entry:
                    self.iconSelector.injectCustomIcon(
                        icon, entry['Hash'],
                        qurl.toString())
        except Exception as err:
            log.debug(f'Could not load favicon: {err}')

    async def fillCategories(self):
        self.ui.category.addItem(iNoCategory())
        self.ui.category.insertSeparator(0)

        for cat in await database.categoriesNames():
            self.ui.category.addItem(cat)

    def onIconSelected(self, iconCid):
        self.iconCid = iconCid

    def onIconEmpty(self):
        self.iconCid = None

    def onSelectIcon(self):
        fps = filesSelectImages()
        if len(fps) > 0:
            ensure(self.setIcon(fps.pop()))

    @ipfsOp
    async def setIcon(self, op, fp):
        entry = await op.addPath(fp, recursive=False)
        if entry:
            cid = entry['Hash']

            if self.iconWidget is None:
                iconWidget = ImageWidget()

                if await iconWidget.load(cid):
                    self.ui.formLayout.insertRow(7, QLabel(''), iconWidget)
                    self.iconCid = cid
                    self.iconWidget = iconWidget
            else:
                if await self.iconWidget.load(cid):
                    self.iconCid = cid

    def onNewCatChanged(self, text):
        self.ui.category.setEnabled(len(text) == 0)

    def accept(self):
        ensure(self.process())

    async def process(self):
        # storageFormatIdx = self.ui.storageFormat.currentIndex()
        storageFormatIdx = 0
        title = self.ui.title.text()

        if len(title) == 0:
            return await messageBoxAsync(iNoTitleProvided())

        # share = self.ui.share.isChecked()
        newCat = self.ui.newCategory.text()
        description = self.ui.description.toPlainText()

        if len(description) > 1024:
            return messageBox('Description is too long')

        if len(newCat) > 0:
            category = cidhelpers.normp(newCat)
        elif self.ui.category.currentText() != iNoCategory():
            category = self.ui.category.currentText()
        else:
            category = None

        if storageFormatIdx == 0:  # LD hashmarks
            if self.ipfsPath.valid:
                uref = self.ipfsPath.ipfsUriRef
            else:
                uref = self.resourceUriRef

            iconUrl = IPFSPath(self.iconCid).ipfsUrl if self.iconCid else None

            imagePath = self.imageSelector.imageIpfsPath

            result = await rdf_hashmarks.addLdHashmark(
                self.ipfsPath if self.ipfsPath.valid else uref,
                title,
                comment=self.ui.comment.text(),
                descr=description,
                iconUrl=iconUrl,
                thumbnailUriRef=imagePath.ipfsUriRef if imagePath else None,
                mimeType=self.mimeType if self.mimeType else None,
                filesStat=self.filesStat,
                schemePreferred=self.schemePreferred,
                graphUri=self.graphUri
            )

            if result is True:
                self.done(0)

                await runDialogAsync(
                    HashmarkIPTagsDialog,
                    uref,
                    graphUri=self.graphUri
                )
            else:
                # TODO. handle error
                pass
        elif storageFormatIdx == 1:  # unused now (old database)
            hashmark = await database.hashmarkAdd(
                self.resourceUrl,
                title=title,
                comment=self.ui.comment.text(),
                description=description,
                icon=self.iconCid,
                category=category,
                share=False,
                pin=self.ui.pinCombo.currentIndex(),
                schemepreferred=self.schemePreferred
            )

            self.done(0)

            await runDialogAsync(
                HashmarkIPTagsDialog,
                hashmark=hashmark
            )


class HashmarkIPTagsDialog(QDialog):
    def __init__(
            self,
            hashmarkUri: URIRef,
            graphUri: str = None,
            parent=None):
        super(HashmarkIPTagsDialog, self).__init__(parent)

        self.app = QApplication.instance()
        self.hashmarkUri = hashmarkUri
        self.graphUri = graphUri

        self.setWindowTitle(iHashmarkIPTagsEdit())

        self.destTags = []

        self.allTagsModel = self.pronto.allTagsModel

        self.destTagsModel = TagsSparQLModel(
            graphUri='urn:ipg:i:love:hashmarks',
            # graphUri='urn:ipg:i',
            rq='HashmarkTags',
            bindings={'hmuri': self.hashmarkUri}
        )

        self.allTagsProxyModel = QSortFilterProxyModel(self)
        self.allTagsProxyModel.setSourceModel(self.allTagsModel)

        self.ui = ui_iptagsmanager.Ui_IPTagsDialog()
        self.ui.setupUi(self)

        self.ui.destTagsView.setModel(self.destTagsModel)
        self.ui.destTagsView.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )
        self.ui.allTagsView.setModel(self.allTagsModel)
        self.ui.allTagsView.doubleClicked.connect(
            self.onTagDoubleClicked
        )

        self.ui.addTagButton.clicked.connect(lambda: ensure(self.addTag()))
        self.ui.lineEditTag.textChanged.connect(self.onTagEditChanged)
        self.ui.lineEditTag.setValidator(
            QRegExpValidator(QRegExp(r'[A-Za-z0-9-_@#]+')))
        self.ui.lineEditTag.setMaxLength(128)
        self.ui.lineEditTag.setClearButtonEnabled(True)

        self.ui.tagItButton.clicked.connect(self.onTagObject)
        self.ui.untagItButton.clicked.connect(partialEnsure(self.untagObject))
        # self.ui.okButton.clicked.connect(lambda: ensure(self.validate()))
        self.ui.okButton.clicked.connect(partialEnsure(self.validate))
        self.ui.noTagsButton.clicked.connect(self.reject)

        self.setMinimumSize(
            self.app.desktopGeometry.width() / 2,
            (2 * self.app.desktopGeometry.height()) / 3
        )

    @property
    def pronto(self):
        return services.getByDotName('ld.pronto')

    def onTagEditChanged(self, text):
        self.allTagsProxyModel.setFilterRegExp(text)
        self.ui.allTagsView.clearSelection()

    def onTagDoubleClicked(self, idx):
        ensure(self.tagObject([idx]))

    def onTagObject(self, idx):
        ensure(self.tagObject())

    async def untagObject(self, *args):
        try:
            for idx in self.ui.destTagsView.selectedIndexes():
                tag = self.destTagsModel.data(
                    idx,
                    SubjectUriRole
                )

                if tag:
                    rdf_hashmarks.ldHashmarkUntag(
                        self.hashmarkUri,
                        URIRef(tag),
                        graphUri=self.graphUri
                    )
        except Exception:
            pass

        self.destTagsModel.update()

    async def tagObject(self, indexes=None):
        indexes = indexes if indexes else self.ui.allTagsView.selectedIndexes()

        for idx in indexes:
            tagUri = self.allTagsModel.data(
                idx,
                SubjectUriRole
            )

            if tagUri:
                rdf_hashmarks.ldHashmarkTag(
                    self.hashmarkUri,
                    URIRef(tagUri),
                    graphUri=self.graphUri
                )

        await self.refreshModels()

    async def refreshModels(self):
        self.allTagsModel.update()
        self.destTagsModel.update()

    async def initDialog(self):
        await self.refreshModels()

    async def addTag(self):
        # TODO
        tagname = self.ui.lineEditTag.text()
        if not tagname:
            return

        rdf_hashmarks.ldHashmarkTag(
            self.hashmarkUri,
            ipTagsFormat(tagname)
        )

        await self.refreshModels()

    async def updateAllTags(self):
        result = list(await rdf_hashmarks.tagsSearch())
        tags = [str(row['tag']) for row in result]

        self.allTagsModel.setStringList(tags)
        self.ui.allTagsView.setModel(self.allTagsProxyModel)
        self.allTagsProxyModel.sort(0)

    async def validate(self, *args):
        self.done(1)

        if 0:
            hmTags = []
            for idx in range(self.destTagsModel.rowCount()):
                hmTags.append(self.destTagsModel.data(
                    idx,
                    Qt.DisplayRole
                ))
            return

            rdf_hashmarks.hashmarkTagsUpdate(
                self.hashmarkUri, hmTags)


class IPTagsSelectDialog(QDialog):
    def __init__(
            self,
            parent=None):
        super().__init__(parent)

        self.app = QApplication.instance()
