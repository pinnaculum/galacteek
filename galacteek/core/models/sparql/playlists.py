from rdflib import URIRef
from rdflib import RDF
from rdflib import Literal

from PyQt5.QtMultimedia import QMediaContent
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QVariant
from PyQt5.QtCore import pyqtSignal

from galacteek.core import uid4
from galacteek.core.models.sparql import SparQLListModel
from galacteek.ipfs.cidhelpers import IPFSPath

from galacteek.ld import ipsContextUri
from galacteek.ld import ipsTermUri
from galacteek.ld.rdf import BaseGraph
from galacteek.ld.iri import superUrn
from galacteek.ld.rdf.resources.multimedia import MultimediaPlaylistResource
from galacteek.ld.rdf.util import literalDtNow

from galacteek.ui.helpers import getIcon


MediaIpfsPathRole = Qt.UserRole + 1
MediaIpfsUrlRole = Qt.UserRole + 2
MediaGatewayedUrlRole = Qt.UserRole + 3


class LDPlayListModel(SparQLListModel):
    """
    Playlist model based on RDF and SparQL
    """

    playlistChanged = pyqtSignal(URIRef, str)

    def __init__(self, graphUri=None, graph=None):
        super().__init__(graphUri=graphUri,
                         graph=graph if graph else BaseGraph())

        self.newPlaylist()

    def emitPlChanged(self):
        self.playlistChanged.emit(self.uri, self.rsc.name)

    def attach(self, rsc: MultimediaPlaylistResource):
        self.rsc = rsc
        self.emitPlChanged()

    def newPlaylist(self):
        self.clearModel()

        try:
            # iService = services.getByDotName('dweb.schemes.i')
            # uri = iService.iriGenObject('MultimediaPlaylist')
            # now = utcDatetime()
            # name = now.strftime('%d-%m-%y (%H:%M)')

            self.setGraph(BaseGraph())

            self.uri = superUrn(f'ipp:playlists:{uid4()}')

            self.rsc = MultimediaPlaylistResource(self.graph, self.uri)
            self.rsc.add(RDF.type, ipsContextUri('MultimediaPlaylist'))
            self.rsc.add(ipsTermUri('numTracks'), Literal(0))
            self.rsc.add(ipsTermUri('dateCreated'),
                         literalDtNow())
        except Exception:
            pass
        else:
            self.emitPlChanged()
            # self.playlistChanged.emit(self.uri, self.rsc.name)

    def mediaForIndex(self, idx):
        try:
            item = self._results[idx.row()]
            p = IPFSPath(str(item['url']))
            assert p.valid is True
        except (KeyError, IndexError):
            return None
        else:
            return QMediaContent(self.app.subUrl(p.objPath))

    def data(self, idx, role=None):
        try:
            item = self._results[idx.row()]
        except (KeyError, IndexError):
            return QVariant(None)

        try:
            if role == Qt.DisplayRole:
                return str(item['name'])
            elif role == Qt.ToolTipRole:
                return str(item['url'])
            elif role == Qt.DecorationRole:
                if item['ttype'] == ipsContextUri('MusicRecording'):
                    return getIcon('multimedia/song.png')
                elif item['ttype'] == ipsContextUri('VideoObject'):
                    return getIcon('multimedia/video.png')
            elif role == MediaIpfsPathRole:
                p = IPFSPath(str(item['url']))
                if p.valid:
                    return p.objPath
        except Exception:
            return QVariant(None)

    async def update(self):
        await self.queryTrack()

    async def queryTrack(self):
        self.clearModel()

        await self.graphQueryAsync('''
          PREFIX gs: <ips://galacteek.ld/>

          SELECT ?ttype ?name ?url ?dateCreated
          WHERE {
            ?uri a gs:MultimediaPlaylist .
            ?uri gs:track ?t .
            OPTIONAL { ?t gs:dateCreated ?dateCreated . } .
            ?t a ?ttype .
            ?t gs:name ?name .
            ?t gs:url ?url .

            FILTER(?uri = ?pluri)
          }
          ORDER BY ASC(?dateCreated)
        ''', bindings={
            'pluri': URIRef(self.rsc.identifier)
        })


class LDPlayListsSearchModel(SparQLListModel):
    def data(self, idx, role=None):
        try:
            item = self._results[idx.row()]
            if role == Qt.DisplayRole:
                return str(item['name'])
            elif role == Qt.UserRole or role == Qt.ToolTipRole:
                return str(item['pluri'])
            elif role == Qt.DecorationRole:
                return getIcon('multimedia/playlist.png')
        except (KeyError, IndexError):
            return QVariant(None)
        except Exception:
            return QVariant(None)

    async def queryPlaylists(self, name):
        self.clearModel()

        await self.graphQueryAsync('''
            PREFIX gs: <ips://galacteek.ld/>

            SELECT ?pluri ?name
            WHERE {
               ?pluri a gs:MultimediaPlaylist .
               ?pluri gs:name ?name .
               FILTER regex (?name, str(?nameSearch), "i")
            }
        ''', bindings={
            'nameSearch': Literal(name)
        })
