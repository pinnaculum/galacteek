from rdflib import Literal
from rdflib import URIRef

from yarl import URL

from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QFormLayout
from PyQt5.QtWidgets import QAbstractItemView

from PyQt5.QtCore import QRegExp
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QUrl
from PyQt5.QtCore import QSortFilterProxyModel
from PyQt5.QtCore import QStringListModel

from galacteek import ensure
from galacteek import partialEnsure
from galacteek import services

from galacteek.config.cmods import app as cmod_app

from galacteek.core.ipfsmarks import *

from galacteek.core.models.sparql.tags import TagsSparQLModel
from galacteek.core.models.sparql.tags import TagMeaningUrlsRole
from galacteek.core.models.sparql import SubjectUriRole

from galacteek.browser.schemes import isEnsUrl
from galacteek.browser.schemes import isHttpUrl
from galacteek.browser.schemes import isGeminiUrl

from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.wrappers import ipfsOp
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.appsettings import *

from galacteek.ld.rdf import hashmarks as rdf_hashmarks
from galacteek.ld.rdf import GraphURIRef
from galacteek.ld.rdf import dbpedia

from ..forms import ui_addhashmarkdialog
from ..forms import ui_iptagsmanager

from .tags import CreateTagDialog

from ..helpers import *
from ..widgets import ImageWidget
from ..widgets import IconSelector
from ..widgets import ImageSelector
from ..widgets import OutputGraphSelectorWidget

from ..i18n import iDoNotPin
from ..i18n import iPinSingle
from ..i18n import iPinRecursive
from ..i18n import iNoTitleProvided
from ..i18n import iHashmarkIPTagsEdit

from ..i18n import iIPTagFetchingMeaning
from ..i18n import iIPTagFetchMeaningError

from ..i18n import iAddHashmark
from ..i18n import iEditHashmark

from ..i18n import iPublicHashmarks
from ..i18n import iPrivateHashmarks
from ..i18n import iHashmarksSearchRoom
from ..i18n import trTodo


def boldLabelStyle():
    return 'QLabel { font-weight: bold; }'


class AddHashmarkDialog(QDialog):
    def __init__(
            self,
            resourceUrl: str,
            title: str,
            description: str,
            langTag: str = None,
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

        self.iconWidget = None
        self.iconCid = None
        self.schemePreferred = schemePreferred

        self.ui = ui_addhashmarkdialog.Ui_AddHashmarkDialog()
        self.ui.setupUi(self)
        self.ui.resourceLabel.setText(self.resourceUrl)
        self.ui.resourceLabel.setStyleSheet(boldLabelStyle())
        self.ui.resourceLabel.setToolTip(self.resourceUrl)
        self.ui.title.setText(title)

        langTagComboBoxInit(self.ui.langtag, default=langTag)

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

    @property
    def selectedLangTag(self):
        return langTagComboBoxGetTag(self.ui.langtag)

    def onOutGraphSelect(self, graphUri: GraphURIRef):
        msg, ico = None, None

        if graphUri.urnLastPart:
            # Should replace this by adding fields (description, etc ..)
            # in each pronto graph

            urnBlock = graphUri.specificCut('i:love:hashmarks:')

            if urnBlock.startswith('private'):
                msg = iPrivateHashmarks(str(graphUri))
                ico = ':/share/icons/key-diago.png'
            elif urnBlock.startswith('search'):
                msg = iHashmarksSearchRoom(urnBlock)
                ico = ':/share/icons/linked-data/peers-linked.png'
            elif urnBlock.startswith('public'):
                msg = iPublicHashmarks(urnBlock)
                ico = ':/share/icons/linked-data/peers-linked.png'
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

    def accept(self):
        ensure(self.process())

    async def process(self):
        title = self.ui.title.text()

        if len(title) == 0:
            return await messageBoxAsync(iNoTitleProvided())

        description = self.ui.description.toPlainText()

        if len(description) > 1024:
            return messageBox('Description is too long')

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
            metaLangTag=self.selectedLangTag,
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
            await messageBoxAsync(trTodo('Error adding hashmark'))


class HashmarkIPTagsDialog(QDialog):
    def __init__(
            self,
            hashmarkUri: URIRef,
            graphUri: str = None,
            parent=None):
        super(HashmarkIPTagsDialog, self).__init__(parent)

        self._tasks = []
        self.app = QApplication.instance()
        self.hashmarkUri = hashmarkUri
        self.graphUri = graphUri

        self.setWindowTitle(iHashmarkIPTagsEdit())

        self.destTags = []

        self.allTagsModel = self.pronto.allTagsModel

        self.destTagsModel = TagsSparQLModel(
            graphUri='urn:ipg:i:love:hashmarks',
            rq='HashmarkTags',
            bindings={
                'hmuri': self.hashmarkUri,
                'langTag': Literal(cmod_app.defaultContentLangTag())
            }
        )

        self.allTagsProxyModel = QSortFilterProxyModel(self)
        self.allTagsProxyModel.setSourceModel(self.allTagsModel)

        self.ui = ui_iptagsmanager.Ui_IPTagsDialog()
        self.ui.setupUi(self)

        self.ui.tagAbstractLabel.setVisible(False)
        self.ui.destTagsView.setModel(self.destTagsModel)
        self.ui.destTagsView.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )
        self.ui.allTagsView.setModel(self.allTagsModel)
        self.ui.allTagsView.clicked.connect(self.onTagClicked)
        self.ui.allTagsView.doubleClicked.connect(
            self.onTagDoubleClicked
        )

        self.ui.createTagButton.clicked.connect(self.onCreateTag)

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

    def setTagAbstract(self, tagAbstract: str):
        self.ui.tagAbstractLabel.setText(tagAbstract)
        self.ui.tagAbstractLabel.setToolTip(tagAbstract)
        self.ui.tagAbstractLabel.setVisible(True)

    def onTagClicked(self, idx):
        if self._tasks:
            [t.cancel() for t in self._tasks]

            self._tasks.clear()

        self._tasks.append(ensure(self.tagMeaningTask(idx)))

    async def tagMeaningTask(self, idx):
        """
        A Tag was clicked. Get the meaning of the tag (the tag abstract),
        store it, and show the meaning in the dialog.
        """

        self.setTagAbstract(iIPTagFetchingMeaning())

        def getAbstract(g, url: URL):
            return g.value(
                subject=URIRef(str(url)),
                predicate=URIRef('http://dbpedia.org/ontology/abstract')
            )

        def dbpediaMeaningUrls():
            """
            Return tag meaning URLs that point to dbpedia resources
            """

            for url in [URL(u) for u in self.allTagsModel.data(
                idx,
                TagMeaningUrlsRole
            ).split(';')]:
                if url.host == 'dbpedia.org':
                    if url.scheme != 'http':
                        url = url.with_scheme('http')

                    yield url

        for url in dbpediaMeaningUrls():
            tagAbstract = getAbstract(self.allTagsModel.graph, url)

            if tagAbstract:
                self.setTagAbstract(tagAbstract)
                return

            try:
                graph = await dbpedia.requestGraph(
                    'DbPediaResourceAbstract',
                    cmod_app.defaultContentLangTag(),
                    f'FILTER (?s = <{url}>)'
                )
                assert graph is not None
            except Exception as err:
                self.ui.tagAbstractLabel.setText(
                    iIPTagFetchMeaningError(err))
            else:
                tagAbstract = getAbstract(graph, url)

                if tagAbstract:
                    # Add the abstract triples
                    for s, p, o in graph:
                        self.allTagsModel.graph.add((s, p, o))

                    self.setTagAbstract(tagAbstract)

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

        await self.refreshModels()

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
        self.destTagsModel.update()

    async def initDialog(self):
        await self.refreshModels()

    async def createTagDialog(self):
        dlg = CreateTagDialog()
        await runDialogAsync(dlg)

        if dlg.result() == 0:
            return
        elif dlg.result() == 1:
            await dlg.create()

    def onCreateTag(self):
        ensure(self.createTagDialog())

    async def updateAllTags(self):
        result = list(await rdf_hashmarks.tagsSearch())
        tags = [str(row['tag']) for row in result]

        self.allTagsModel.setStringList(tags)
        self.ui.allTagsView.setModel(self.allTagsProxyModel)
        self.allTagsProxyModel.sort(0)

    async def validate(self, *args):
        self.done(1)


class IPTagsSelectDialog(QDialog):
    def __init__(self,
                 parent=None):
        super(IPTagsSelectDialog, self).__init__(parent)

        self.app = QApplication.instance()

        self.allTagsModel = self.pronto.allTagsModel
        self.destTagsModel = QStringListModel([])

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

        self.ui.tagItButton.clicked.connect(self.onTagObject)
        self.ui.untagItButton.clicked.connect(partialEnsure(self.untagObject))
        self.ui.okButton.clicked.connect(self.validate)
        self.ui.noTagsButton.clicked.connect(self.reject)

        self.setMinimumSize(
            self.app.desktopGeometry.width() / 2,
            (2 * self.app.desktopGeometry.height()) / 3
        )

    @property
    def pronto(self):
        return services.getByDotName('ld.pronto')

    @property
    def selectedTagsList(self):
        return self.destTagsModel.stringList()

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
                    Qt.DisplayRole
                )

                if tag:
                    newList = self.destTagsModel.stringList()
                    newList.remove(tag)
                    self.destTagsModel.setStringList(newList)
        except Exception:
            pass

    async def tagObject(self, indexes=None):
        indexes = indexes if indexes else self.ui.allTagsView.selectedIndexes()

        for idx in indexes:
            tagUri = self.allTagsModel.data(
                idx,
                SubjectUriRole
            )

            if tagUri and tagUri not in self.destTagsModel.stringList():
                self.destTagsModel.setStringList(
                    self.destTagsModel.stringList() + [tagUri]
                )

    async def refreshModels(self):
        pass

    async def initDialog(self):
        await self.refreshModels()

    def validate(self):
        self.done(1)
