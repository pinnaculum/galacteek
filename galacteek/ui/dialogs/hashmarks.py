import asyncio

from typing import List

from rdflib import Literal
from rdflib import URIRef

from yarl import URL

from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QAbstractItemView

from PyQt5.QtCore import QRegExp
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import QUrl
from PyQt5.QtCore import QSortFilterProxyModel
from PyQt5.QtCore import QStringListModel

from PyQt5.QtGui import QRegExpValidator

from galacteek import ensure
from galacteek import partialEnsure
from galacteek import services

from galacteek.config.cmods import app as cmod_app

from galacteek.core.ipfsmarks import *

from galacteek.core.models.sparql.tags import TagsSparQLModel
from galacteek.core.models.sparql.tags import TagMeaningUrlsRole
from galacteek.core.models.sparql import SubjectUriRole

from galacteek.core.models.sparql.kg import kgConstructModel

from galacteek.core.models.sparql.kg import RdfLabelRole
from galacteek.core.models.sparql.kg import RdfEnglishLabelRole

from galacteek.browser.schemes import isEnsUrl
from galacteek.browser.schemes import isHttpUrl
from galacteek.browser.schemes import isGeminiUrl

from galacteek.ipfs.ipfsops import *
from galacteek.ipfs.wrappers import ipfsOp
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.appsettings import *

from galacteek.ld.rdf import hashmarks as rdf_hashmarks
from galacteek.ld.rdf import tags as rdf_tags
from galacteek.ld.rdf import GraphURIRef
from galacteek.ld.rdf import dbpedia

from ..forms import ui_addhashmarkdialog
from ..forms import ui_iptagsmanager

from .tags import CreateTagDialog

from ..helpers import *
from ..notify import uiNotify
from ..widgets import IconSelector
from ..widgets import ImageSelector
from ..widgets import OutputGraphSelectorWidget
from ..widgets import AnimatedLabel
from ..widgets.ld import LDSearcher

from ..clips import RotatingCubeClipSimple

from ..i18n import iDoNotPin
from ..i18n import iPinSingle
from ..i18n import iPinRecursive
from ..i18n import iNoTitleProvided
from ..i18n import iHashmarkIPTagsEdit

from ..i18n import iIPTagFetchingMeaning
from ..i18n import iIPTagFetchMeaningError
from ..i18n import iIPTagInvalid

from ..i18n import iAddHashmark
from ..i18n import iEditHashmark

from ..i18n import iPublicHashmarks
from ..i18n import iPrivateHashmarks
from ..i18n import iHashmarksSearchRoom
from ..i18n import trTodo

from ..i18n import iKgSearchForTags
from ..i18n import iKgSearching
from ..i18n import iKgSearchNoResultsFor
from ..i18n import iKgSearchBePatient0
from ..i18n import iKgSearchBePatient1
from ..i18n import iKgSearchBePatient2
from ..i18n import iKgSearchBePatient3


def boldLabelStyle():
    return 'QLabel { font-weight: bold; }'


reTagName = QRegExp(r"[\w\-\_\s]{1,64}")


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

        self.ui.extraGridLayout.addWidget(QLabel('Icon'), 0, 0)
        self.ui.extraGridLayout.addWidget(self.iconSelector, 0, 1)

        # Img
        self.imageSelector = ImageSelector(parent=self)

        self.ui.extraGridLayout.addWidget(QLabel('Thumbnail'), 1, 0)
        self.ui.extraGridLayout.addWidget(self.imageSelector, 1, 1)

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
        self._ldstasks = []
        self._tagSearchTextLast = None

        self.app = QApplication.instance()
        self.hashmarkUri: URIRef = hashmarkUri
        self.graphUri: str = graphUri

        self.ui = ui_iptagsmanager.Ui_IPTagsDialog()
        self.ui.setupUi(self)

        self.setWindowTitle(iHashmarkIPTagsEdit())

        self.destTags: list = []

        # List of tag URIs already associated with the hashmark (on load)
        self.initialTagsUris: List[str] = []

        self.destTagsModel = TagsSparQLModel(
            graphUri='urn:ipg:i:love:hashmarks',
            rq='HashmarkTags',
            bindings={
                'hmuri': self.hashmarkUri,
                'langTag': Literal(cmod_app.defaultContentLangTag())
            }
        )
        self.destTagsModel.modelReset.connect(self.onDestTagsReset)

        self.allTagsModel = QSortFilterProxyModel(self)
        self.allTagsModel.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.allTagsModel.setSourceModel(self.pronto.allTagsModel)

        self.statusLabel = AnimatedLabel(RotatingCubeClipSimple())
        self.statusLabel.clip.setScaledSize(QSize(32, 32))

        langTagComboBoxInit(self.ui.searchLanguage)
        self.ui.searchLanguage.currentTextChanged.connect(
            self.onChangeSearchLanguage
        )

        self.ldSearcher = LDSearcher(parent=self)
        self.ldSearcher.setPlaceholderText(
            iKgSearchForTags(self.contentLangTag))
        self.ldSearcher.textChanged.connect(self.onLdSearchChanged)
        self.ldSearcher.textEdited.connect(self.onLdSearchEdit)
        self.ldSearcher.resultActivated.connect(self.onLdResultActivated)
        self.ldSearcher.setValidator(QRegExpValidator(reTagName))

        self.editTimer = QTimer(self)
        self.editTimer.setSingleShot(True)
        self.editTimer.timeout.connect(partialEnsure(self.ldSearchTag))

        self.ui.hLayoutLdSearch.addWidget(self.statusLabel)
        self.ui.hLayoutLdSearch.addWidget(self.ldSearcher)

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
        self.ui.okButton.clicked.connect(partialEnsure(self.validate))
        self.ui.noTagsButton.clicked.connect(self.reject)

        self.setMinimumSize(
            self.app.desktopGeometry.width() * 0.7,
            self.app.desktopGeometry.height() * 0.8,
        )

        self.ldSearcher.setFocus(Qt.OtherFocusReason)

    @property
    def pronto(self):
        return services.getByDotName('ld.pronto')

    @property
    def tagSearchText(self):
        return self.ldSearcher.text()

    @property
    def tagSearchTextLast(self):
        return self._tagSearchTextLast

    @property
    def sourceModel(self):
        return self.allTagsModel.sourceModel()

    @property
    def contentLangTag(self):
        return langTagComboBoxGetTag(self.ui.searchLanguage)

    @property
    def dbSource(self):
        # return self.ui.dbSource.currentText()

        if self.ui.dbSource.currentIndex() == 0:
            return 'wikidata'
        elif self.ui.dbSource.currentIndex() == 1:
            return 'dbpedia'

    def destTagsUris(self) -> List[str]:
        """
        Returns a list of the selected tags, as URI strings
        """
        return [str(ref) for ref in
                self.destTagsModel.tagUris()]

    def onDestTagsReset(self) -> None:
        """
        Destination tags model was reset: store the URIs of the
        tags already associated with the hashmark. This is then
        compared to the final list when the dialog is validated.
        """

        if not self.initialTagsUris:
            self.initialTagsUris = self.destTagsUris()

    def cancelTasks(self) -> None:
        [t.cancel() for t in self._tasks + self._ldstasks]
        self._tasks.clear()
        self._ldstasks.clear()

    def cancelLdSearchTasks(self) -> None:
        [t.cancel() for t in self._ldstasks]
        self._ldstasks.clear()

    def onChangeSearchLanguage(self, langText: str) -> None:
        self.ldSearcher.setPlaceholderText(
            iKgSearchForTags(langText))

    def onLdResultActivated(self, idx) -> None:
        # RDF Label for the user's language
        label = self.ldSearcher.model.data(idx, RdfLabelRole)

        # XXX: get the English label
        labelEn = self.ldSearcher.model.data(idx, RdfEnglishLabelRole)

        def created(future):
            try:
                name = future.result()
                assert isinstance(name, str)
                self.ldSearcher.setText(name)
            except AssertionError:
                pass
            except Exception:
                pass

        if label and labelEn:
            f = ensure(self.createTagFromKgUri(
                self.contentLangTag,
                label,
                labelEn,
                URIRef(self.ldSearcher.model.data(idx, SubjectUriRole)))
            )
            f.add_done_callback(created)

    async def createTagFromKgUri(self,
                                 lang: str,
                                 label: str,
                                 labelEn: str,
                                 rscuri: URIRef) -> str:
        """
        Create a tag from a knowledge graph resource URI
        """

        # XXX: **always** use the English RDF label when we create the URI
        tagUri = rdf_tags.tagUriFromLabel(labelEn)
        if not tagUri:
            await messageBoxAsync(iIPTagInvalid())
            return None

        await rdf_tags.tagCreate(
            tagUri,
            tagNames={
                'en': label
            },
            tagDisplayNames={
                'en': labelEn,
                lang: label
            },
            meanings=[{
                '@type': 'TagMeaning',
                '@id': str(rscuri)
            }],
            watch=False
        )

        return self.tagSearchTextLast

    def onLdSearchChanged(self, text: str) -> None:
        self.allTagsModel.setFilterRegExp(text)
        self.ui.allTagsView.clearSelection()

    def onLdSearchEdit(self, text: str) -> None:
        """
        Called when the tag search line is edited by the user.
        Set the filter regexp on the tags proxy model.
        """

        self.statusLabel.stopClip()
        self.editTimer.stop()

        if text:
            self._tagSearchTextLast = text

            self.allTagsModel.setFilterRegExp(text)
            self.ui.allTagsView.clearSelection()

            self.editTimer.start(800)

    async def ldSearchTag(self) -> None:
        self.cancelLdSearchTasks()
        self.ldSearcher.resetModel()

        tagName = self.tagSearchText

        if not tagName:
            return

        def searchFinished(fut):
            self.cancelLdSearchTasks()
            self.statusLabel.stopClip()
            self.ui.searchStatusLabel.setText('')

            try:
                model = fut.result()
                assert model is not None
                assert len(model._results) > 0

                self.ldSearcher.feedModel(model)
            except Exception as err:
                self.ui.searchStatusLabel.setText(
                    iKgSearchNoResultsFor(tagName, str(err))
                )
            else:
                uiNotify('tagSearchSuccess')

        self.ui.searchStatusLabel.setText(
            iKgSearching(tagName, self.dbSource)
        )

        if self.dbSource == 'wikidata':
            future = ensure(kgConstructModel(
                'WDResourceSearch',
                self.contentLangTag,  # label language
                self.contentLangTag,  # abstract language
                tagName.lower().strip(),
                db='wikidata',
                returnFormat='json'
            ))
        elif self.dbSource == 'dbpedia':
            future = ensure(kgConstructModel(
                'DbPediaResourceSearch',
                self.contentLangTag,  # label language
                self.contentLangTag,  # abstract language
                tagName.lower().strip(),
                db='dbpedia',
                returnFormat='graph'
            ))

        self.statusLabel.startClip()

        prog = ensure(self.searchStatusTask())

        future.add_done_callback(searchFinished)

        self._ldstasks.append(future)
        self._ldstasks.append(prog)

    async def searchStatusTask(self) -> None:
        msgs = [
            iKgSearchBePatient0(),
            iKgSearchBePatient1(),
            iKgSearchBePatient2(),
            iKgSearchBePatient3()
        ]

        for x in range(0, len(msgs)):
            await asyncio.sleep(5)

            self.ui.searchStatusLabel.setText(msgs[x])

    def setTagAbstract(self, tagAbstract: str) -> None:
        self.ui.tagAbstractLabel.setText(tagAbstract)

        self.ui.tagAbstractLabel.setToolTip(
            self.sourceModel.abstractSummarize(tagAbstract, 20)
        )

        self.ui.tagAbstractLabel.setVisible(True)

    def onTagClicked(self, idx) -> None:
        if self._tasks:
            [t.cancel() for t in self._tasks]

            self._tasks.clear()

        self._tasks.append(ensure(self.tagMeaningTask(idx)))

    async def tagMeaningTask(self, idx) -> None:
        """
        A Tag was clicked. Get the meaning of the tag (the tag abstract),
        store it, and show the abstract in the dialog.
        """

        uri = self.allTagsModel.data(
            idx,
            SubjectUriRole
        )

        self.setTagAbstract(iIPTagFetchingMeaning(uri))

        def getAbstract(g, url: URL):
            if url.host == 'dbpedia.org':
                return g.value(
                    subject=URIRef(str(url)),
                    predicate=URIRef('http://dbpedia.org/ontology/abstract')
                )
            elif url.host.endswith('wikidata.org'):
                return g.value(
                    subject=URIRef(str(url)),
                    predicate=URIRef('http://schema.org/description')
                )

        def meaningUrls():
            """
            Return tag meaning URLs that point to dbpedia or
            wikidata resources
            """

            for url in [URL(u) for u in self.allTagsModel.data(
                idx,
                TagMeaningUrlsRole
            ).split(';')]:
                if url.host in ['dbpedia.org',
                                'www.wikidata.org',
                                'wikidata.org']:
                    if url.scheme != 'http':
                        url = url.with_scheme('http')

                    yield url

        for url in meaningUrls():
            tagAbstract = getAbstract(self.sourceModel.graph, url)

            if tagAbstract:
                self.setTagAbstract(tagAbstract)
                return

            try:
                if url.host == 'dbpedia.org':
                    graph = await dbpedia.request(
                        'DbPediaResourceAbstract',
                        cmod_app.defaultContentLangTag(),
                        str(url),
                        db='dbpedia'
                    )
                    assert graph is not None
                elif url.host in ['wikidata.org', 'www.wikidata.org']:
                    graph = await dbpedia.request(
                        'WDResourceDesc',
                        cmod_app.defaultContentLangTag(),
                        str(url),
                        db='wikidata'
                    )
                    assert graph is not None
                else:
                    raise ValueError('Cannot fetch description')
            except Exception as err:
                self.ui.tagAbstractLabel.setText(
                    iIPTagFetchMeaningError(err))
            else:
                tagAbstract = getAbstract(graph, url)

                if tagAbstract:
                    # Add the abstract triples
                    for s, p, o in graph:
                        self.sourceModel.graph.add((s, p, o))

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

                # Watch this tag.
                rdf_tags.tagWatch(URIRef(tagUri))

        await self.refreshModels()

    async def refreshModels(self):
        self.destTagsModel.update()

    async def initDialog(self):
        await self.refreshModels()

    async def createTagDialog(self):
        dlg = CreateTagDialog(name=self.tagSearchText)
        await runDialogAsync(dlg)

        self.cancelTasks()

        if dlg.result() == 0:
            return
        elif dlg.result() == 1:
            await dlg.create()

    def onCreateTag(self):
        ensure(self.createTagDialog())

    async def validate(self, *args):
        self.cancelTasks()

        # Compute the list of itag URIs that the hashmark was tagged with
        # during the lifetime of this dialog (a simple diff between the
        # final tags list and the initial list), then update the hashmark
        # manager button's menu for those new tags only.

        selectedUris = self.destTagsUris()

        if self.initialTagsUris and selectedUris:
            diff = list(set(selectedUris) - set(self.initialTagsUris))

            if diff:
                ensure(self.app.mainWindow.hashmarkMgrButton.updateMenu(
                    onlyTags=diff
                ))

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
            self.app.desktopGeometry.width() * 0.7,
            self.app.desktopGeometry.height() * 0.8,
        )

    @property
    def pronto(self):
        return services.getByDotName('ld.pronto')

    @property
    def selectedTagsList(self):
        return self.destTagsModel.stringList()

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
